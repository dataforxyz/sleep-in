#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bin_src="$repo_dir/bin/sleep-in"
bin_dst="$HOME/.local/bin/sleep-in"
binding='bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in'
hypr_bindings="$HOME/.config/hypr/bindings.conf"

install -Dm755 "$bin_src" "$bin_dst"
echo "Installed $bin_dst"

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
