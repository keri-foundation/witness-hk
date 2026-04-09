# Ansible Host-First Witness Deployment

This directory owns the pilot inventory, controller-side preflight, host
convergence, post-bootstrap verification, and operator inspection commands for
the host-first witness deployment.

## Architecture

```
systemd
  └── circusd-witness.service
        └── circusd (Circus process manager)
              └── keripy-witness watcher
                    └── run-keripy-witness.sh  →  keri runWitness(...)
```

Ansible owns the machine state: packages, users, directories, Python venv,
editable checkouts of `keripy` and `hio`, rendered configs, and the systemd
unit. Circus owns the process lifecycle after the host is prepared.

## Prerequisites

- Ansible 2.14+ on the operator workstation
- 1Password CLI (`op`) signed in to your account
- `community.general` collection — install with:

  ```bash
  ansible-galaxy collection install community.general
  ```

### SSH Agent Setup

> **Primary platform: macOS.** The operator workflow is designed and tested on
> macOS using the native 1Password SSH agent. Linux is supported but is a
> secondary target — see below.

**macOS (primary)**

1. In 1Password, go to **Settings → Developer → SSH Agent** and enable it.
2. No further SSH config is needed. `with-op-ssh-agent.sh` falls back to the
   standard macOS socket at
   `~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock`
   automatically.

**Linux**

1. In 1Password, go to **Settings → Developer → SSH Agent** and enable it.
2. The default socket path is `~/.1password/agent.sock`.
   `with-op-ssh-agent.sh` falls back to this path automatically.
3. If your setup uses a different agent (forwarded agent, `gnome-keyring`,
   custom `ssh-agent`), export `SSH_AUTH_SOCK` before running any make
   targets and the wrapper will use it as-is.
4. The `ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT` environment variable can override
   the detected socket path if your 1Password agent socket is in a
   non-standard location.

## First-Time Setup

1. Copy the secret-reference template and fill in your 1Password references:

   ```bash
   cp op.env.example op.env
   # edit op.env — replace YOUR_VAULT / YOUR_ITEM placeholders
   ```

   `op.env` is git-ignored. Never commit a filled-in `op.env`.

2. Add a `host_vars/<your-host>.yml` following the pattern in
   `inventories/pilot/host_vars/witness-do-01.yml`.

3. Add the host to `inventories/pilot/hosts.yml` under `witness_hosts`.

4. Review the defaults in `inventories/pilot/group_vars/witness_hosts.yml`
   and override any values that differ for your environment.

5. Run the preflight check:

   ```bash
   ./with-op-ssh-agent.sh --no-ssh-agent \
     ansible-playbook -i inventories/pilot/hosts.yml playbooks/witness-preflight.yml
   ```

## Operator Workflow

### From the repository root (recommended)

```bash
make witness-preflight   # validate 1Password env vars — no SSH needed
make witness-check       # preflight + ping + bootstrap dry-run
make witness-apply       # preflight + full bootstrap
make witness-verify      # post-bootstrap validation
make witness-status      # systemd + Circus status
make witness-logs        # tail stdout and stderr logs
```

### Direct playbook invocation

Run from this directory (`ansible/`):

```bash
# Validate inventory without opening SSH
./with-op-ssh-agent.sh --no-ssh-agent \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/witness-preflight.yml

# Ping the host
./with-op-ssh-agent.sh \
  ansible -i inventories/pilot/hosts.yml witness-do-01 -m ping

# Dry-run bootstrap
./with-op-ssh-agent.sh \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/witness-bootstrap.yml --check --diff

# Apply bootstrap
./with-op-ssh-agent.sh \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/witness-bootstrap.yml

# Verify
./with-op-ssh-agent.sh \
  ansible-playbook -i inventories/pilot/hosts.yml playbooks/witness-verify.yml
```

## Authentication

SSH authentication uses the native 1Password SSH agent — no private keys are
exported or copied. Controller-side variables (`ansible_user`, `ansible_host`,
`ansible_become_password`) are injected as environment variables through a
short-lived `op run` subprocess via `with-op-ssh-agent.sh`.

The current validated escalation path on the pilot host is:

1. SSH as the `keri` user (non-root)
2. `su` to `root` with the separate root password from 1Password

`sudo` is not assumed to be configured for the `keri` user.

## Lint

```bash
ansible-lint playbooks/witness-bootstrap.yml \
            playbooks/witness-preflight.yml \
            playbooks/witness-verify.yml \
            roles/witness_host
```

The checked-in `.ansible-lint.yml` uses the `production` profile in offline
mode. Install the linter with `pipx install ansible-lint`.

## Deployment Evidence Checklist

For AI-assisted deployment work, do not treat a successful apply as proof that
the deployment is correct. Capture evidence from the controller, the host, and
the running service.

### Minimum Evidence For A Deployment Change

1. **Task scope**
  - record what was intended to change
  - note what was not supposed to change
2. **Controller-side validation**
  - run `ansible-lint`
  - run `make witness-preflight`
  - run `make witness-check`
3. **Apply evidence**
  - run `make witness-apply`
  - keep the terminal output or summarize the important state changes
4. **Post-apply verification**
  - run `make witness-verify`
  - run `make witness-status`
  - run `make witness-logs`
5. **Human review of host state**
  - confirm the service manager sees the unit as healthy
  - confirm Circus sees the witness process as healthy
  - confirm the wrapper-backed runtime contract still matches the expected launch path
  - confirm expected ports or sockets are reachable
  - confirm recent logs are reviewed using the current boot or current start window, not just the tail of append-only files
  - confirm a smoke check passed where the lane supports one

### What Counts As Enough Evidence

At minimum, the operator should be able to say:

1. what changed
2. what commands were run
3. what outputs were reviewed directly
4. whether the host converged cleanly
5. whether any ambiguity remains

### Operational Notes

1. A running PID is not enough. Treat `systemctl status` as one input, not the final proof.
2. If logs are append-only, tie any error review to the current run window before concluding the service is still broken.
3. If repeated runs do not converge cleanly, stop and investigate instead of normalizing the drift.
4. Save or summarize the evidence in the task record or PR notes so the review trail survives after the terminal scrollback is gone.

## Directory Layout

```
ansible/
├── .ansible-lint.yml
├── ansible.cfg
├── op.env.example          # template for 1Password secret references
├── README.md
├── with-op-ssh-agent.sh    # op run + SSH agent wrapper
├── inventories/
│   └── pilot/
│       ├── hosts.yml
│       ├── group_vars/
│       │   └── witness_hosts.yml   # shared defaults for all witness hosts
│       └── host_vars/
│           └── witness-do-01.yml   # pilot host overrides
├── playbooks/
│   ├── witness-preflight.yml   # inventory validation (no SSH)
│   ├── witness-bootstrap.yml   # full host convergence
│   └── witness-verify.yml      # post-bootstrap health checks
└── roles/
  └── witness_host/
    ├── handlers/main.yml
    ├── tasks/main.yml
    └── templates/
      ├── circus-witness.ini.j2
      ├── circusd-witness.service.j2
      └── run-keripy-witness.sh.j2
```

## What the Bootstrap Does

1. Installs system packages: `git`, `rsync`, `build-essential`,
   `libsodium-dev`, `python3.14`, `python3.14-venv`
2. Creates the `keri` system user and group
3. Creates directories: `/opt`, `/etc/keri`, `/usr/local/var/keri`,
   `/var/log/keri/witness`
4. Clones `keripy` (`/opt/keripy`) and `hio` (`/opt/hio`) from GitHub
5. Creates a Python 3.14 venv at `/opt/keripy/.venv`
6. Installs `circus` and editable installs of `hio` and `keripy` into the venv
7. Renders `/opt/keripy/ops/run-keripy-witness.sh` from template
8. Renders `/etc/keri/circus-witness.ini` from template (IPC-only control socket)
9. Renders `/etc/systemd/system/circusd-witness.service` from template
10. Enables and starts the `circusd-witness` systemd unit
