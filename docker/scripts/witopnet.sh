#!/bin/bash
# Container entrypoint for a single witness-hk (witopnet) replica running as one pod
# in a StatefulSet. Each replica hosts exactly one witness identity, so the only thing
# that varies per replica is the externally-advertised hostname, which is derived here
# from the pod's ordinal rather than passed in per-replica by the chart.
#
# Required env vars (set by the Helm chart):
#   WITOPNET_BASE_DOMAIN   Base domain for per-instance hostnames. This pod becomes
#                          reachable at witness-<ordinal>.<WITOPNET_BASE_DOMAIN>.
#   WITOPNET_HTTP_PORT     Witness server port (see .Values.ports.witness).
#   WITOPNET_BOOT_PORT     Boot/management server port (see .Values.ports.boot).
set -euo pipefail

# A StatefulSet sets $HOSTNAME to "<statefulset-name>-<ordinal>" automatically.
ordinal="${HOSTNAME##*-}"
external_host="witness-${ordinal}.${WITOPNET_BASE_DOMAIN}"

# keripy's Configer resolves config at {config-dir}/keri/cf/{base}/{name}.json with
# base="main" (default) and name="witopnet" — hence the "main/" segment below.
mkdir -p /usr/local/var/keri/cf/main
dt="$(date -u +%Y-%m-%dT%H:%M:%S.%6N+00:00)"
cat > /usr/local/var/keri/cf/main/witopnet.json <<EOF
{
  "dt": "${dt}",
  "witopnet": {
    "dt": "${dt}",
    "curls": ["https://${external_host}/"]
  }
}
EOF

# Can't be set from outside the container reliably; production runs this at process
# start for the same reason (scripts/witopnet-sample.sh).
ulimit -S -n 65536

# TLS is terminated at the Ingress, matching how curls above is "https://" while this
# process itself only speaks HTTP. Boot host binds 0.0.0.0 (not 127.0.0.1) so the
# kubelet's readiness/liveness probes, which hit the pod IP from outside the container's
# network namespace, can reach it — the boot port is still never exposed by a Service
# or Ingress outside the cluster.
exec witopnet marshal start \
  --config-dir /usr/local/var \
  --host 0.0.0.0 \
  --http "${WITOPNET_HTTP_PORT}" \
  --boothost 0.0.0.0 \
  --bootport "${WITOPNET_BOOT_PORT}"
