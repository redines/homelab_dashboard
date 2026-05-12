#!/usr/bin/env bash
set -euo pipefail

agent_sock="${HOME}/.ssh/devcontainer-agent.sock"
agent_env="${HOME}/.ssh/devcontainer-agent.env"
default_key="${HOME}/.ssh/id_ed25519"

if ! command -v ssh-agent >/dev/null || ! command -v ssh-add >/dev/null; then
  echo "Warning: ssh-agent or ssh-add is not installed on the host"
  exit 1
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

agent_is_available() {
  local status=0
  SSH_AUTH_SOCK="${agent_sock}" ssh-add -l >/dev/null 2>&1 || status=$?
  case "${status}" in
    0 | 1) return 0 ;;
    *) return 1 ;;
  esac
}

if ! agent_is_available; then
  rm -f "${agent_sock}"
  ssh-agent -a "${agent_sock}" > "${agent_env}"
  chmod 600 "${agent_env}"
fi

if ! SSH_AUTH_SOCK="${agent_sock}" ssh-add -l >/dev/null 2>&1; then
  if [ -r "${default_key}" ]; then
    SSH_AUTH_SOCK="${agent_sock}" ssh-add "${default_key}" || true
  else
    echo "Warning: ${default_key} does not exist; SSH agent is running without a key"
  fi
fi
