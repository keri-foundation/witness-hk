#!/bin/bash
# Launch the Witness Operational Network.
#
# Runs the witness server (default: 5632) and boot/management server (default: 5631).
# The witness server binds to the external host; the boot server stays on localhost.
#
# Environment variable overrides (all optional):
#   WITOPNET_VENV        Path to a venv activate script. Sourced if the file exists;
#                        skipped with a warning if set but not found; ignored if unset.
#                        (default: not set — assumes caller is already in the right env)
#
#   WITOPNET_CONFIG_DIR  Directory containing keri/cf/witopnet.json.
#                        (default: the scripts/ directory, so local dev works after 'source env.sh')
#
#   WITOPNET_BASE        Relative keystore base prefix. Must NOT be an absolute path.
#                        (default: witopnet)
#
#   WITOPNET_HOST        External host for the witness server.
#                        (default: DigitalOcean private IP from metadata API, fallback 127.0.0.1)
#
#   WITOPNET_BOOT_HOST   Host for the boot/management server. Keep on localhost in production.
#                        (default: 127.0.0.1)
#
#   WITOPNET_HTTP_PORT   Witness server port. (default: 5632)
#   WITOPNET_BOOT_PORT   Boot/management server port. (default: 5631)
#
# Local dev usage:
#   source scripts/env.sh
#   ./scripts/witopnet-sample.sh
#
# Production usage:
#   WITOPNET_VENV=/opt/keri-foundation/venv/bin/activate \
#   WITOPNET_CONFIG_DIR=/opt/keri-foundation/config \
#   ./scripts/witopnet-sample.sh

# Resolve the directory this script lives in, whether or not env.sh has been sourced.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# --- Venv activation ---
if [[ -n "${WITOPNET_VENV:-}" ]]; then
    if [[ -f "${WITOPNET_VENV}" ]]; then
        # shellcheck disable=SC1090
        source "${WITOPNET_VENV}"
    else
        echo "WARN: WITOPNET_VENV set but not found at '${WITOPNET_VENV}', skipping activation." >&2
    fi
fi

# --- Config directory ---
# KERI's Configer appends keri/cf/ internally, so this should point to the directory
# *above* keri/cf/ (e.g. scripts/, not scripts/keri/cf/).
[[ -z "${WITOPNET_CONFIG_DIR:-}" ]] && ConfigDir="${SCRIPT_DIR}" || ConfigDir="${WITOPNET_CONFIG_DIR}"

# --- Keystore base (must be relative) ---
[[ -z "${WITOPNET_BASE:-}" ]] && Base="witopnet" || Base="${WITOPNET_BASE}"

# --- External host for the witness server ---
# On DigitalOcean, the private IP is read from the metadata API.
# Falls back to 127.0.0.1 if the metadata API is unreachable (e.g. local dev).
if [[ -n "${WITOPNET_HOST:-}" ]]; then
    Host="${WITOPNET_HOST}"
else
    Host=$(curl -sf --max-time 2 \
        http://169.254.169.254/metadata/v1/interfaces/private/0/ipv4/address \
        2>/dev/null || echo "127.0.0.1")
fi

# --- Boot server host (localhost only in production) ---
[[ -z "${WITOPNET_BOOT_HOST:-}" ]] && BootHost="127.0.0.1" || BootHost="${WITOPNET_BOOT_HOST}"

# --- Ports ---
[[ -z "${WITOPNET_HTTP_PORT:-}" ]] && HttpPort="5632" || HttpPort="${WITOPNET_HTTP_PORT}"
[[ -z "${WITOPNET_BOOT_PORT:-}" ]] && BootPort="5631" || BootPort="${WITOPNET_BOOT_PORT}"

# --- Production resource limits ---
export KERI_BASER_MAP_SIZE=1099511627776
ulimit -S -n 65536

# --- Launch ---
export DEBUG_WITOPNET=1
witopnet marshal start \
    --config-dir "${ConfigDir}" \
    --base "${Base}" \
    --host "${Host}" \
    --http "${HttpPort}" \
    --boothost "${BootHost}" \
    --bootport "${BootPort}"