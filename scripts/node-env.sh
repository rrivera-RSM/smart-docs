#!/usr/bin/env bash

ensure_smartdocs_node() {
  if node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 20 || (major === 20 && minor >= 9) ? 0 : 1)' 2>/dev/null; then
    return 0
  fi

  local account_dir
  account_dir="$(getent passwd "$(id -un)" | cut -d: -f6)"

  if [ -s "$account_dir/.nvm/nvm.sh" ]; then
    export NVM_DIR="$account_dir/.nvm"
    # shellcheck source=/dev/null
    . "$NVM_DIR/nvm.sh"
    nvm use --silent >/dev/null
  fi

  if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 20 || (major === 20 && minor >= 9) ? 0 : 1)' 2>/dev/null; then
    echo "SmartDocs requiere Node.js 20.9 o superior. Ejecuta 'nvm use' en apps/web." >&2
    return 1
  fi
}
