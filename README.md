# witopnet — Witness Operational Network

`witopnet` is a [KERI](https://github.com/WebOfTrust/keri) witness service that provides authenticated event receipting for KERI identifiers. It exposes a dual-server HTTP architecture:

- **Boot server** (default port `5631`): management API for provisioning and deleting witnesses
- **Witness server** (default port `5632`): KERI event processing, receipting, OOBI resolution, and mailbox services

Witnesses are provisioned dynamically via the boot API and secured with TOTP-based two-factor authentication before receipting events.

## Requirements

- Python >= 3.12.6
- `libsodium` (required by the `keri` package)

### Installing libsodium

**macOS:**
```bash
brew install libsodium
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libsodium-dev
```

## Installation

### From PyPI

```bash
pip install witopnet
```

### For development

```bash
git clone https://github.com/keri-foundation/witness-hk.git
cd witness-hk
pip install -e ".[dev]"
```

## Configuration

The witness server is configured via a KERI config file. A sample config is provided at `scripts/keri/cf/witopnet.json`:

```json
{
  "dt": "2022-01-20T12:57:59.823350+00:00",
  "witopnet": {
    "dt": "2022-01-20T12:57:59.823350+00:00",
    "curls": ["http://127.0.0.1:5632/"]
  }
}
```

The `curls` field sets the controller URL(s) advertised by the witness. Place your config file in a directory you will pass to `--config-dir`.

## Running the witness

### CLI

After installation, the `witopnet` CLI is available:

```bash
witopnet marshal start \
  --config-dir /path/to/config \
  --base witopnet \
  --host 0.0.0.0 \
  --http 5632 \
  --boothost 127.0.0.1 \
  --bootport 5631
```

> **Note:** `--config-dir` must point to the directory *above* `keri/cf/` — KERI appends `keri/cf/` internally when locating `witopnet.json`. `--base` must be a relative path, not absolute.

**Key flags:**

| Flag | Default | Description |
|---|---|---|
| `--host` / `-o` | `127.0.0.1` | Host the witness server listens on |
| `--http` / `-H` | `5632` | Port the witness server listens on |
| `--boothost` / `-bh` | `127.0.0.1` | Host the boot server listens on |
| `--bootport` / `-bp` | `5631` | Port the boot server listens on |
| `--base` / `-b` | `""` | Path prefix for the KERI keystore |
| `--config-dir` / `-c` | — | Directory containing KERI config files |
| `--config-file` | — | Config filename override |
| `--loglevel` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `--logfile` | — | Path to write log output |

Set `DEBUG_WITOPNET=1` in your environment to print full tracebacks on errors.

### Submitting events to witnesses

The `marshal submit` subcommand submits a controller's current event to its witnesses for receipting:

```bash
witopnet marshal submit \
  --name <keystore-name> \
  --alias <identifier-alias> \
  [--passcode <passcode>]
```

## HTTP API

### Boot server (`localhost:5631`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/witnesses` | Provision a new witness for a controller AID. Body: `{"aid": "<qb64-AID>"}`. Returns `{cid, eid, oobis}`. |
| `DELETE` | `/witnesses/{eid}` | Delete a witness by its endpoint identifier. |
| `GET` | `/health` | Health check, returns `204 No Content`. |

### Witness server (`localhost:5632`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Submit a KERI event (KEL/EXN/TEL/QRY) with CESR attachments. |
| `PUT` | `/` | Push raw CESR bytes into the inbound stream. |
| `POST` | `/aids` | Register a controller AID with 2FA. Body: `multipart/form-data` with `kel`, optional `delkel`, optional `secret`. Returns `{totp, oobi}`. |
| `POST` | `/receipts` | Request a witness receipt for a KEL event. Requires `Authorization` header with TOTP. |
| `GET` | `/receipts` | Retrieve a stored receipt by `pre` and `sn` or `said`. |
| `GET` | `/ksn` | Get the key state notice for a prefix. |
| `GET` | `/log` | Replay KEL events for a prefix. |
| `GET` | `/oobi/{aid}` | OOBI resolution endpoint. |
| `GET` | `/oobi/{aid}/{role}` | OOBI with role. |
| `GET` | `/oobi/{aid}/{role}/{eid}` | OOBI with role and participant EID. |

## Scripts

The `scripts/` directory contains shell scripts for local development and integration testing. All scripts that reference `${WITOPNET_SCRIPT_DIR}` require you to source `env.sh` first.

### `env.sh`

Sets `WITOPNET_SCRIPT_DIR` to the absolute path of the `scripts/` directory. Source this before running any other script:

```bash
source scripts/env.sh
```

### `witopnet-sample.sh`

Launches the witness and boot servers. Works for both local development (after `source scripts/env.sh`) and production deployment.

**Important:** `--config-dir` must point to the directory *above* `keri/cf/` — KERI appends `keri/cf/` internally. For local dev this is the `scripts/` directory; for production it is wherever `keri/cf/witopnet.json` lives one level up.

| Variable | Default | Description |
|---|---|---|
| `WITOPNET_VENV` | *(unset)* | Path to a venv `activate` script. Sourced if the file exists; warns and skips if set but not found; ignored if unset (assumes caller is already in the right env). |
| `WITOPNET_CONFIG_DIR` | `scripts/` directory | Directory containing `keri/cf/witopnet.json` (one level above `keri/cf/`). |
| `WITOPNET_BASE` | `witopnet` | Relative keystore base prefix. Must not be an absolute path. |
| `WITOPNET_HOST` | DigitalOcean private IP, fallback `127.0.0.1` | External host the witness server binds to. Reads from the DO metadata API automatically; falls back to `127.0.0.1` if unreachable (e.g. local dev). |
| `WITOPNET_BOOT_HOST` | `127.0.0.1` | Host the boot/management server binds to. Keep on localhost in production. |
| `WITOPNET_HTTP_PORT` | `5632` | Witness server port. |
| `WITOPNET_BOOT_PORT` | `5631` | Boot/management server port. |

Local dev (no env vars needed after sourcing `env.sh`):

```bash
source scripts/env.sh
./scripts/witopnet-sample.sh
```

Production example:

```bash
WITOPNET_VENV=/opt/keri-foundation/venv/bin/activate \
WITOPNET_CONFIG_DIR=/opt/keri-foundation/config \
./scripts/witopnet-sample.sh
```

### `controller.sh`

Demonstrates provisioning a single witness and rotating a controller's key event log onto it. Requires the witness server to be running and `kli` (KERI CLI) to be installed.

```bash
source scripts/env.sh
bash scripts/controller.sh
```

Steps performed:
1. Initializes a `controller` keystore and creates an inception event
2. Provisions a new witness via `POST /witnesses`
3. Resolves the witness OOBI
4. Authenticates the controller with the witness (`kli witness authenticate`)
5. Rotates the controller AID to add the witness
6. Rotates again to demonstrate subsequent rotation
7. Provisions a second witness and repeats the process

### `controller-multi.sh`

Similar to `controller.sh` but provisions two witnesses simultaneously and performs a multi-witness rotation in a single step.

```bash
source scripts/env.sh
bash scripts/controller-multi.sh
```

## Testing

Install the package in editable mode with dev dependencies, then run pytest:

```bash
pip install -e ".[dev]"
pytest tests/
```

Tests are located under `tests/witopnet/app/` and cover the aiding, indirecting, and witnessing modules. The test suite uses temporary in-memory KERI keystores so no external services are required.

To run a specific test file:

```bash
pytest tests/witopnet/app/test_witnessing.py -v
```

## License

Apache-2.0. See [LICENSE](LICENSE).