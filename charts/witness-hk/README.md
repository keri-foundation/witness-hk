# Deploying the `witness-hk` chart

Deploys `witness-hk` (witopnet) as a set of independently-addressable KERI witness nodes,
matching the redundancy properties of the production Ansible/droplet deployment (one LMDB
keystore and one externally-resolvable hostname per witness) on top of a single Kubernetes
StatefulSet.

## What gets deployed

- **`<release>` StatefulSet** — `replicaCount` (default 3) fully independent pods, each with
  its own PVC (`volumeClaimTemplates`, not a shared PVC) and its own witness identity/keystore.
  `podManagementPolicy: Parallel` — replicas have no startup ordering dependency on each other.
- **`<release>-headless` Service** — required by `statefulset.spec.serviceName`; also gives
  in-cluster callers (e.g. hkapi/hkweb) direct per-pod DNS to each replica's boot API:
  `<release>-N.<release>-headless.<namespace>.svc.cluster.local:<ports.boot>`.
- **`<release>-N` Services** (one per ordinal) — ClusterIP, each selecting exactly pod N via the
  `statefulset.kubernetes.io/pod-name` label the StatefulSet controller sets automatically. These
  exist only to give the Ingress below a per-replica backend.
- **`<release>` Ingress** (only if `ingress.enabled: true`) — one host rule per ordinal,
  `witness-N.<baseDomain>` routed to `<release>-N` on the `witness` port. The boot port is never
  referenced by the Ingress — it stays ClusterIP-only, matching production reality that the
  boot/management API (which creates/deletes witness identities) must not be publicly reachable.

This chart deploys infrastructure only. Actual witness provisioning (`POST /witnesses` against a
replica's boot API) is a separate, external, runtime concern — matching how `castellan-oobi` is
deployed as bare stateless infra with no bootstrap Job.

## Required fields — the chart will not install without these

| Field | What it is |
|---|---|
| `image.repository` / `image.tag` | Where to pull the `witness-hk` image from. Empty by default. |
| `baseDomain` | Base domain for per-instance external hostnames. Instance N is reachable at `witness-N.<baseDomain>` — this gets baked into that replica's KERI config as its OOBI-advertised `curls` entry on first boot. |

If either is missing, `helm install`/`helm template` fails fast with a `required(...)` error
rather than deploying something broken.

## Ingress and TLS

`ingress.enabled` defaults to `false`. When enabled, set:

```yaml
ingress:
  enabled: true
  className: nginx            # or whatever your cluster uses
  tls:
    enabled: true
    secretName: witness-wildcard-tls   # a single wildcard cert covering *.<baseDomain>
```

A single wildcard cert is recommended (and is what the chart's single `tls:` block assumes) since
one Ingress resource here produces N hosts (`witness-0.<baseDomain>` … `witness-(N-1).<baseDomain>`)
— templating N distinct per-ordinal cert secrets would need N separate `tls:` entries instead.

## Gateway API (`HTTPRoute`) instead of Ingress

If your cluster routes external traffic through the [Gateway API](https://gateway-api.sigs.k8s.io/)
(Envoy Gateway, Istio, GKE Gateway, etc.) rather than a classic Ingress controller, leave
`ingress.enabled: false` — this chart never creates `HTTPRoute` objects, so there's nothing to
disable on that side, and no risk of a competing resource.

The chart's external-routing contract is the same regardless of which mechanism attaches to it:

- one `<release>-N` Service per ordinal (already created unconditionally), on the `witness` port
- N hostnames of the form `witness-N.<baseDomain>`
- TLS covering `*.<baseDomain>`, terminated wherever your Gateway's listener already terminates it
  — an `HTTPRoute` doesn't carry its own `tls:` block the way this chart's Ingress does; that's the
  parent `Gateway`'s job.

One important difference from Ingress: a single `HTTPRoute`'s `hostnames` all share the *same*
`rules`/backend — you can't route hostname A to backend A and hostname B to backend B within one
`HTTPRoute` object, the way this chart's Ingress template does with one host rule per ordinal. So
you need **one `HTTPRoute` per ordinal**, each with a single hostname and a single `backendRef`,
mirroring the per-ordinal Services this chart already creates:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: witness-hk-0
  namespace: <your-namespace>   # same namespace as the chart release
spec:
  parentRefs:
    - name: <your-gateway>
      namespace: <gateway-namespace>   # omit if the Gateway is in the same namespace
  hostnames:
    - witness-0.<baseDomain>
  rules:
    - backendRefs:
        - name: witness-hk-0   # <release>-0
          port: 5632            # ports.witness
```

Repeat for every ordinal 0..`replicaCount-1`, changing only the hostname, the `HTTPRoute` name,
and the backend Service name. If the `HTTPRoute` lives in a different namespace than the `Gateway`
it attaches to, you'll also need a `ReferenceGrant` in the `Gateway`'s namespace authorizing that
cross-namespace attachment.

## PVC retention on scale changes

`persistentVolumeClaimRetentionPolicy` is hardcoded to `{whenDeleted: Retain, whenScaled: Retain}`.
PVCs are named deterministically (`keri-data-<statefulset-name>-<ordinal>`), so scaling
`replicaCount` down and back up reattaches the same PVC to the same ordinal, restoring that
witness's keys/KEL intact rather than starting it fresh — a witness identity's private key
material is irreplaceable, so accidental scale-down must not destroy it.

Two caveats:

1. This only protects ordinals that have previously existed — scaling to a higher replica count
   than ever seen still creates fresh, empty PVCs for the new ordinals (a new witness identity).
2. `whenDeleted: Retain` only enables reattachment on a later `helm install` if the new release
   produces the same StatefulSet name (same release name, via `witnesshk.fullname`) — a
   differently-named release will leave the old PVCs orphaned, requiring manual re-binding.

## Everything else (sane defaults — only touch if you know why)

| Field | Default | When to change it |
|---|---|---|
| `ports.boot` / `ports.witness` | `5631` / `5632` | Only if something else on your nodes conflicts. `boot` is never exposed outside the cluster regardless. |
| `replicaCount` | `3` | Scale to however many independent witopnet nodes (failure domains) you need — not witness count. Each node already hosts an arbitrary number of witnesses via its own boot API (`POST /witnesses`), independent of replica count. See PVC retention caveats above before scaling down. |
| `imagePullSecrets` | `[]` | If your image registry is private. |
| `persistence.storageClassName` | `""` (cluster default) | Set explicitly if your cluster has no default `StorageClass`, or you want a specific one. |
| `persistence.size` | `5Gi` | Bump if you expect a large per-witness keystore. |
| `persistence.accessMode` | `ReadWriteOnce` | Leave alone — each pod owns its own PVC, RWO is sufficient. |
| `resources` | `{}` (no limits) | Set standard Kubernetes `requests`/`limits` once you know actual load. |
| `serviceAccount.create` / `.name` | `false` / `""` | Leave as-is unless your cluster's RBAC policy requires workloads to use a dedicated, non-default ServiceAccount. |

## Minimal `values.yaml` overlay

```yaml
image:
  repository: weboftrust/witness-hk
  tag: v1.3.6-dev

baseDomain: witness.your-domain.example

ingress:
  enabled: true
  className: nginx
  tls:
    enabled: true
    secretName: witness-wildcard-tls

persistence:
  storageClassName: your-storage-class  # omit if your cluster has a default
```

Validate before installing:
```bash
helm lint charts/witness-hk -f your-values.yaml
helm template witness-hk charts/witness-hk -f your-values.yaml | less
```
