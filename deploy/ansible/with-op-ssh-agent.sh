#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# with-op-ssh-agent.sh
#
# Primary platform: macOS
#   SSH authentication uses the native 1Password SSH agent. The default socket
#   path is the macOS-specific location set by the 1Password desktop app.
#
# Linux support:
#   Also works on Linux if the 1Password SSH agent is running. The default
#   socket path on Linux is ~/.1password/agent.sock. You can override the
#   socket location by setting ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT in your
#   environment before calling this script, or by pointing SSH_AUTH_SOCK at
#   any already-running SSH agent that holds the correct key.
#
#   If you use a non-1Password SSH agent on Linux (e.g. ssh-agent, gnome-keyring,
#   or a forwarded agent), export SSH_AUTH_SOCK before running this script and
#   the agent-detection step will skip the 1Password socket lookup entirely.
# -----------------------------------------------------------------------------
set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OP_RUN_ENV_FILE="${OP_RUN_ENV_FILE:-${SCRIPT_DIR}/op.env}"

# Resolve the default 1Password SSH agent socket for the current OS.
# macOS: set by the 1Password desktop app under ~/Library/Group Containers/
# Linux: set by the 1Password desktop app under ~/.1password/
# Override by setting ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT in your environment.
if [[ -z "${ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT:-}" ]]; then
    case "$(uname -s)" in
        Darwin)
            ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
            ;;
        Linux)
            ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT="$HOME/.1password/agent.sock"
            ;;
        *)
            ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT=""
            ;;
    esac
fi

require_ssh_agent=1

if [[ ${1:-} == "--no-ssh-agent" ]]; then
    require_ssh_agent=0
    shift
fi

if [[ $# -eq 0 ]]; then
    echo "usage: $0 [--no-ssh-agent] <ansible command> [args ...]" >&2
    exit 1
fi

if ! command -v op >/dev/null 2>&1; then
    echo "op CLI is required" >&2
    exit 1
fi

# Only require ssh-add when we are actually going to open an SSH connection.
if [[ "$require_ssh_agent" -eq 1 ]]; then
    if ! command -v ssh-add >/dev/null 2>&1; then
        echo "ssh-add is required" >&2
        exit 1
    fi
fi

if [[ ! -f "$OP_RUN_ENV_FILE" ]]; then
    echo "op run env file is required: $OP_RUN_ENV_FILE" >&2
    echo "Copy op.env.example to op.env and fill in your 1Password secret references." >&2
    exit 1
fi

configure_1password_ssh_agent() {
    # If SSH_AUTH_SOCK is already set and the agent has keys loaded, use it as-is.
    # This covers: forwarded agents, gnome-keyring, custom macOS/Linux agents, etc.
    if [[ -n ${SSH_AUTH_SOCK:-} ]] && ssh-add -l >/dev/null 2>&1; then
        return 0
    fi

    # Try the platform-specific 1Password agent socket.
    if [[ -n "${ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT:-}" ]] && [[ -S "$ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT" ]]; then
        export SSH_AUTH_SOCK="$ONEPASSWORD_SSH_AUTH_SOCK_DEFAULT"
    fi

    if [[ -z ${SSH_AUTH_SOCK:-} ]] || ! ssh-add -l >/dev/null 2>&1; then
        cat >&2 <<'EOF'
1Password SSH agent is not ready.

macOS: Enable the SSH agent in 1Password Settings → Developer → SSH Agent.
Linux: Enable the SSH agent in 1Password Settings → Developer → SSH Agent.
        The default socket path is ~/.1password/agent.sock.

Alternatively, export SSH_AUTH_SOCK pointing to any SSH agent that holds
the correct key before calling this script.
EOF
        exit 1
    fi
}

if [[ "$require_ssh_agent" -eq 1 ]]; then
    configure_1password_ssh_agent
fi

exec op run --env-file="$OP_RUN_ENV_FILE" -- "$@"
