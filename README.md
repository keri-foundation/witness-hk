# witopnet — Witness Operational Network

`witopnet` is a [KERI](https://github.com/WebOfTrust/keri) witness service that provides authenticated event receipting for KERI identifiers. It exposes a dual-server HTTP architecture:

- **Boot server** (default port `5631`): management API for provisioning and deleting witnesses
- **Witness server** (default port `5632`): KERI event processing, receipting, OOBI resolution, and mailbox services

Witnesses are provisioned dynamically via the boot API and secured with TOTP-based two-factor authentication before receipting events.

For provisioning, authenticating and receipting flows (including POC1 use), see [POC1-WITNESS-HK-OPERATIONS.md](POC1-WITNESS-HK-OPERATIONS.md).

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

The witness server is configured via a KERI config file, `witopnet.json`, read from `<config-dir>/keri/cf/main/witopnet.json`. A sample config is provided at `scripts/keri/cf/main/witopnet.json`:

```json
{
  "dt": "2022-01-20T12:57:59.823350+00:00",
  "witopnet": {
    "dt": "2022-01-20T12:57:59.823350+00:00",
    "curls": ["http://127.0.0.1:5632/"]
  }
}
```

The `curls` field sets the controller URL(s) advertised by the witness (the first entry is used for OOBIs). Place your config file at `keri/cf/main/witopnet.json` inside the directory you pass to `--config-dir`.

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

> **Note:** `--config-dir` must point to the directory *above* `keri/` — KERI appends `keri/cf/main/` internally when locating `witopnet.json`. `--base` must be a relative path, not absolute, and applies to the keystores, not the config file.

**Key flags:**

| Flag | Default | Description |
|---|---|---|
| `--host` / `-o` | `127.0.0.1` | Host the witness server listens on |
| `--http` / `-H` | `5632` | Port the witness server listens on |
| `--boothost` / `-bh` | `127.0.0.1` | Host the boot server listens on |
| `--bootport` / `-bp` | `5631` | Port the boot server listens on |
| `--base` / `-b` | `""` | Path prefix for the KERI keystore |
| `--config-dir` / `-c` | — | Directory containing `keri/cf/main/witopnet.json` |
| `--loglevel` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `--logfile` | — | Path to write log output |
| `--keypath` / `--certpath` / `--cafilepath` | — | TLS private key, certificate and CA bundle, if the servers should terminate TLS themselves |

Set `DEBUG_WITOPNET=1` in your environment to print full tracebacks on errors.

Other environment variables: `WITOPNET_ESCROW_TOCK` (escrow processing interval in seconds, default `0.5`), `WITOPNET_DOIST_TOCK` (main loop tick, default `0.03125`) and `KERI_BASER_MAP_SIZE` (LMDB map size in bytes; set high in production).

### Submitting events to witnesses

The `marshal submit` subcommand submits a controller's current event to its witnesses for receipting:

```bash
witopnet marshal submit \
  --name <keystore-name> \
  --alias <identifier-alias> \
  [--base <keystore-base>] \
  [--passcode <21-character-passcode>] \
  [--aeid <non-transferable-prefix>] \
  [--config <config-dir>] \
  [--force]
```

`--force` re-sends receipt requests even when the current event already has a full complement of receipts.

## HTTP API

### Boot server (`localhost:5631`)

The boot server has **no authentication**. Keep it bound to localhost (or cluster-internal) and never expose it externally.

| Method | Path | Description |
|---|---|---|
| `POST` | `/witnesses` | Provision a new witness for a controller AID. Body: `{"aid": "<qb64-AID>"}`. Returns `{cid, eid, oobis}`. Each call creates a new witness; one process hosts any number of them. |
| `DELETE` | `/witnesses/{eid}` | Permanently delete a witness by its endpoint identifier. Returns `204`, or `404` if unknown. |
| `GET` | `/health` | Health check, returns `204 No Content`. |

### Witness server (`localhost:5632`)

Every endpoint except `/oobi` requires a `CESR-DESTINATION` header containing the AID (`eid`) of the witness being addressed, since one process hosts many witnesses. A missing header or unknown AID is rejected (`400`, or `404` on `POST /`). A witness only serves the controller AID it was provisioned for.

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | Submit a KERI event (KEL/EXN/TEL/QRY) with CESR attachments. An optional `Authorization` header (format below) makes the event trusted; without it the event is parsed as untrusted and normally escrowed. A `qry` for `mbx` returns a server-sent-event mailbox stream. |
| `PUT` | `/` | Accepted for compatibility (returns `204`); the body is not processed. Use `POST /`. |
| `POST` | `/aids` | Register a controller AID for 2FA. Body: `multipart/form-data` with `kel` (inception KEL), optional `delkel` (delegator KEL), optional `secret` (TOTP seed; random if omitted). Returns `{totp, oobi}`, plus `totps` (one entry per controller key, in inception key order) when the AID has more than one key. Calling it again replaces the stored secret. |
| `POST` | `/receipts` | Request a witness receipt for a KEL event. Requires the `Authorization` header (format below). Returns `200` with the receipt, `202` if the event is escrowed, `403` if the AID is not permitted, `412` if the AID never called `/aids`. |
| `GET` | `/receipts` | Retrieve a stored receipt by `pre` and `sn` or `said`. |
| `GET` | `/ksn` | Get the key state notice for `pre` (404 until fully witnessed). |
| `GET` | `/log` | Replay KEL events for `pre` (optional `s`, `a`, `fn`). |
| `GET` | `/oobi/{aid}` | OOBI resolution endpoint. `aid` may be the witness or its controller (the latter only once fully witnessed). |
| `GET` | `/oobi/{aid}/{role}` | OOBI with role. |
| `GET` | `/oobi/{aid}/{role}/{eid}` | OOBI with role and participant EID. |

**`Authorization` header format:** `<6-digit-otp>#<ISO-8601 timestamp the OTP was generated for>`. The timestamp must be within the last 10 minutes. An invalid or missing value is not an error in itself: the event is treated as untrusted, which typically shows up as a `202` or a missing receipt.

## Scripts

The `scripts/` directory contains shell scripts for local development and integration testing. All scripts that reference `${WITOPNET_SCRIPT_DIR}` require you to source `env.sh` first.

### `env.sh`

Sets `WITOPNET_SCRIPT_DIR` to the absolute path of the `scripts/` directory. Source this before running any other script:

```bash
source scripts/env.sh
```

### `witopnet-sample.sh`

Launches the witness and boot servers. Works for both local development (after `source scripts/env.sh`) and production deployment.

**Important:** `--config-dir` must point to the directory *above* `keri/` — KERI appends `keri/cf/main/` internally. For local dev this is the `scripts/` directory; for production it is the directory containing `keri/cf/main/witopnet.json`.

| Variable | Default | Description |
|---|---|---|
| `WITOPNET_VENV` | *(unset)* | Path to a venv `activate` script. Sourced if the file exists; warns and skips if set but not found; ignored if unset (assumes caller is already in the right env). |
| `WITOPNET_CONFIG_DIR` | `scripts/` directory | Directory containing `keri/cf/main/witopnet.json` (one level above `keri/`). |
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

Demonstrates provisioning a single witness and rotating a controller's key event log onto it. Requires the witness server to be running and `kli` (KERI CLI) to be installed. This is a local demo: it targets `localhost:5631`, uses a fixed salt and controller AID, and `kli rotate --authenticate` pauses to prompt for the TOTP code (or pass `--code <eid>:<otp>`).

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