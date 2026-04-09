SHELL := /bin/bash

ROOT_DIR     := $(CURDIR)
ANSIBLE_DIR  := $(ROOT_DIR)/ansible
ANSIBLE_WRAPPER  := $(ANSIBLE_DIR)/with-op-ssh-agent.sh
ANSIBLE_INVENTORY := inventories/pilot/hosts.yml
ANSIBLE_PLAYBOOK  := ansible-playbook -i $(ANSIBLE_INVENTORY)
ANSIBLE_ADHOC     := ansible -i $(ANSIBLE_INVENTORY)
ONEPASSWORD_SSH_AUTH_SOCK ?= $(HOME)/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock
WITNESS_HOST              ?= witness-do-01
WITNESS_LOG_LINES         ?= 40
WITNESS_SYSTEMD_SERVICE   ?= circusd-witness
WITNESS_CIRCUSCTL_BIN     ?= /opt/keripy/.venv/bin/circusctl
WITNESS_CIRCUS_ENDPOINT   ?= ipc:///var/run/keri-circus/ctrl.sock

define require_witness_host
[[ "$(WITNESS_HOST)" =~ ^[A-Za-z0-9_.-]+$$ ]] || { \
	echo "Invalid WITNESS_HOST: $(WITNESS_HOST)" >&2; \
	echo "Expected a single inventory hostname containing only letters, digits, dot, underscore, or dash." >&2; \
	exit 1; \
}
endef

define require_witness_log_lines
[[ "$(WITNESS_LOG_LINES)" =~ ^[1-9][0-9]*$$ ]] || { \
	echo "Invalid WITNESS_LOG_LINES: $(WITNESS_LOG_LINES)" >&2; \
	echo "Expected WITNESS_LOG_LINES to be a positive integer." >&2; \
	exit 1; \
}
endef

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available make targets
	@echo
	@echo "Available commands for witness-hk:"
	@echo
	@awk 'BEGIN {FS = ":.*?##"; printf "Usage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo

##@ Witness Deployment

.PHONY: witness-preflight
witness-preflight: ## Validate 1Password-backed inventory values without opening SSH
	@cd "$(ANSIBLE_DIR)" && "$(ANSIBLE_WRAPPER)" --no-ssh-agent \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-preflight.yml

.PHONY: witness-ping
witness-ping: ## Check SSH connectivity to the configured witness host
	@$(require_witness_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -m ping'

.PHONY: witness-check
witness-check: ## Run preflight, ping, and bootstrap dry-run in one auth batch
	@$(require_witness_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/witness-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-bootstrap.yml --check --diff'

.PHONY: witness-apply
witness-apply: ## Run preflight and apply the witness bootstrap in one auth batch
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/witness-preflight.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-bootstrap.yml'

.PHONY: witness-verify
witness-verify: ## Run the post-bootstrap witness verification playbook
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/witness-verify.yml'

.PHONY: witness-all
witness-all: ## Run preflight, ping, apply, and verify in one auth batch
	@$(require_witness_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/witness-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-bootstrap.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-verify.yml'

.PHONY: witness-status
witness-status: ## Show systemd and Circus watcher status for the witness host
	@$(require_witness_host)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -b -m shell -a '\''systemctl status $(WITNESS_SYSTEMD_SERVICE) --no-pager --lines=20; printf "\\n=== circusctl ===\\n"; $(WITNESS_CIRCUSCTL_BIN) --endpoint $(WITNESS_CIRCUS_ENDPOINT) status'\'''

.PHONY: witness-logs
witness-logs: ## Tail witness stdout and stderr logs from the host
	@$(require_witness_host)
	@$(require_witness_log_lines)
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -b -m shell -a '\''printf "=== stdout ===\\n"; tail -n $(WITNESS_LOG_LINES) /var/log/keri/witness/stdout.log; printf "\\n=== stderr ===\\n"; tail -n $(WITNESS_LOG_LINES) /var/log/keri/witness/stderr.log'\'''
