SHELL := /bin/bash

ROOT_DIR     := $(CURDIR)
ANSIBLE_DIR  := $(ROOT_DIR)/deploy/ansible
ANSIBLE_WRAPPER  := $(ANSIBLE_DIR)/with-op-ssh-agent.sh
ANSIBLE_INVENTORY := inventories/pilot/hosts.yml
ANSIBLE_PLAYBOOK  := ansible-playbook -i $(ANSIBLE_INVENTORY)
ANSIBLE_ADHOC     := ansible -i $(ANSIBLE_INVENTORY)
ONEPASSWORD_SSH_AUTH_SOCK ?= $(HOME)/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock
WITNESS_HOST      ?= witness-do-01
WITNESS_LOG_LINES ?= 40

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
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -m ping'

.PHONY: witness-check
witness-check: ## Run preflight, ping, and bootstrap dry-run in one auth batch
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
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_PLAYBOOK) playbooks/witness-preflight.yml && \
		$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -m ping && \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-bootstrap.yml && \
		$(ANSIBLE_PLAYBOOK) playbooks/witness-verify.yml'

.PHONY: witness-status
witness-status: ## Show systemd and Circus watcher status for the witness host
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -b -m shell -a '\''systemctl status circusd-witness --no-pager --lines=20; printf "\\n=== circusctl ===\\n"; /opt/keripy/.venv/bin/circusctl --endpoint ipc:///var/run/keri-circus/ctrl.sock status'\'''

.PHONY: witness-logs
witness-logs: ## Tail witness stdout and stderr logs from the host
	@cd "$(ANSIBLE_DIR)" && SSH_AUTH_SOCK="$${SSH_AUTH_SOCK:-$(ONEPASSWORD_SSH_AUTH_SOCK)}" "$(ANSIBLE_WRAPPER)" \
		bash -lc '$(ANSIBLE_ADHOC) "$(WITNESS_HOST)" -b -m shell -a '\''printf "=== stdout ===\\n"; tail -n $(WITNESS_LOG_LINES) /var/log/keri/witness/stdout.log; printf "\\n=== stderr ===\\n"; tail -n $(WITNESS_LOG_LINES) /var/log/keri/witness/stderr.log'\'''
