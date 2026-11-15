#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
binding='bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in'
hypr_bindings="$HOME/.config/hypr/bindings.conf"
mako_config="$HOME/.config/mako/config"
mako_include='include=~/.config/mako/sleep-in.conf'

for dependency in systemctl systemd-run journalctl flock python3 wl-copy; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    echo "Missing required command: $dependency" >&2
    exit 1
  fi
done

install -Dm755 "$repo_dir/bin/sleep-in" "$HOME/.local/bin/sleep-in"
install -Dm755 "$repo_dir/bin/sleep-in-fire" "$HOME/.local/bin/sleep-in-fire"
install -Dm755 "$repo_dir/bin/sleep-timer-status" "$HOME/.local/bin/sleep-timer-status"
install -Dm755 "$repo_dir/bin/sleep-timer-menu" "$HOME/.local/bin/sleep-timer-menu"
echo "Installed Sleep In helpers to $HOME/.local/bin"

# Quattro owns its notifications and Lua bindings; leave legacy Mako/config
# setup to older installations. Print a binding instead of rewriting user Lua.
if [[ -f "$HOME/.config/hypr/hyprland.lua" ]]; then
  echo 'Quattro: add this to ~/.config/hypr/bindings.lua if needed:'
  echo 'o.bind("SUPER + CTRL + ALT + S", "Schedule suspend", "~/.local/bin/sleep-in")'
  exit 0
fi

install -Dm644 "$repo_dir/mako/sleep-in.conf" "$HOME/.config/mako/sleep-in.conf"
if [[ -f "$mako_config" ]]; then
  if ! grep -Fqx "$mako_include" "$mako_config"; then
    backup="$mako_config.bak.$(date +%s)"
    cp "$mako_config" "$backup"
    printf '\n# Sleep In click-to-copy failure diagnostics\n%s\n' "$mako_include" >>"$mako_config"
    echo "Added notification actions to $mako_config (backup: $backup)"
  fi
else
  printf '%s\n' "$mako_include" >"$mako_config"
fi
if command -v makoctl >/dev/null 2>&1 && [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  makoctl reload
fi

if [[ -f "$hypr_bindings" ]]; then
  if grep -Fqx "$binding" "$hypr_bindings"; then
    echo "Hyprland binding already present in $hypr_bindings"
  elif grep -Eiq '^\s*bindd?\s*=\s*SUPER[[:space:]]+CTRL[[:space:]]+ALT\s*,\s*S\s*,' "$hypr_bindings"; then
    echo "Found an existing Super+Ctrl+Alt+S binding in $hypr_bindings; leaving it unchanged." >&2
    echo "Add this manually if you want to replace it:" >&2
    echo "$binding" >&2
  else
    backup="$hypr_bindings.bak.$(date +%s)"
    cp "$hypr_bindings" "$backup"
    {
      printf '\n# Sleep In\n'
      printf '%s\n' "$binding"
    } >>"$hypr_bindings"
    echo "Added binding to $hypr_bindings (backup: $backup)"
  fi
else
  mkdir -p "$(dirname "$hypr_bindings")"
  printf '%s\n' "$binding" >"$hypr_bindings"
  echo "Created $hypr_bindings with Sleep In binding"
fi

if command -v hyprctl >/dev/null 2>&1 && [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
  hyprctl reload >/dev/null || true
  hyprctl configerrors || true
fi
