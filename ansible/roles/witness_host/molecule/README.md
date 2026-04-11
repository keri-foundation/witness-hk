# Molecule Integration Tests — witness_host Role

Validates the Ansible role under real systemd hardening, keeping the local
integration lane aligned with the proven DigitalOcean Ubuntu 25.10 baseline and
the role's Python 3.14 runtime floor.

## Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Docker Desktop | 28.x+ | Daemon must be running |
| Python 3.12+ | — | For Molecule itself |
| molecule | ≥ 5.1.0 | `pip install -r molecule/requirements.txt` |
| molecule-plugins[docker] | ≥ 23.5.3 | Docker driver |

Install Molecule deps from the role root:

```bash
pip install -r molecule/requirements.txt
```

Molecule's Galaxy prerun resolves dependency files relative to the role root, so
the role keeps them at `molecule/requirements.yml` and
`molecule/collections.yml`.

## DigitalOcean parity

The current production proof host reports Ubuntu 25.10 (`questing`), so the
scenario builds a custom systemd-ready image from `ubuntu:25.10`. That image
also installs `python3.14` and `python3.14-venv` so the local validation lane
matches the current witness runtime floor.

## Quick start

From the repo root:

```bash
make molecule-test
make molecule-converge
make molecule-verify
make molecule-destroy
make molecule-login
```

Or from the role directory directly:

```bash
cd ansible/roles/witness_host
molecule test
```

## Scenario structure

- `molecule/default/molecule.yml` configures the Docker driver and inline test vars
- `molecule/default/prepare.yml` refreshes apt metadata before package install
- `molecule/default/converge.yml` reuses the shared `ansible/playbooks/witness-bootstrap.yml`
- `molecule/default/verify.yml` reuses the shared `ansible/playbooks/witness-verify.yml`
- `molecule/default/Dockerfile.j2` builds the Ubuntu 25.10 systemd image

The tracked `make molecule-test` path uses a custom Molecule `test_sequence`
that runs `syntax`, `create`, `prepare`, `converge`, `verify`, and `destroy`.
It intentionally skips Molecule's default idempotence step because this role's
integration target is a host-shaped systemd deployment that clones source
checkouts and installs editable local packages during converge.

## What verify checks

The shared verify playbook asserts:

1. `circusd-witness.service` is active and enabled
2. Circus IPC socket and stdout/stderr logs exist
3. `circusctl status` reports `keripy-witness`
4. The witness child process stays alive across two samples
5. The HTTP and TCP listeners bind on the expected ports
6. The rendered unit includes hardening directives and `/usr/local/var/keri`
7. Fresh stdout has no `Permission denied` errors
8. `/usr/local/var/keri` is writable by the service user
9. `HOME` is set inside the Circus env block

## Platform notes

- Base image: `ubuntu:25.10`
- Requires privileged mode and `cgroupns_mode: host` for systemd-in-Docker
- The role clones `hio` and `keripy` during converge, so network access is
  required unless the scenario is adapted to a pre-seeded image later