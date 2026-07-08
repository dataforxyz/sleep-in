# Sleep In

Small Omarchy/Hyprland helper for scheduling system suspend from a keyboard shortcut.

Press `Super` + `Ctrl` + `Alt` + `S`, enter a duration like `90`, `30m`, `2h`, or `1h30`, and the machine will suspend after that delay.

## What it does

- Prompts for a delay with `omarchy-menu-input`.
- Parses minutes, hours, or hour+minute inputs.
- Schedules a user timer using `systemd-run --user --on-active=...`.
- When the timer fires, asks Hyprland to spawn `systemctl --no-ask-password suspend` from the active desktop session.
- Sends a desktop notification with the scheduled suspend time.
- Pings Waybar with `RTMIN+11` so a sleep-timer module can refresh, if you have one.

## Files

```text
bin/sleep-in          # prompt + timer scheduler
bin/sleep-in-fire     # timer target that requests suspend through Hyprland
hypr/sleep-in.conf    # Hyprland binding snippet
install.sh            # installer for ~/.local/bin and ~/.config/hypr/bindings.conf
```

## Install

```bash
git clone https://github.com/dataforxyz/sleep-in.git
cd sleep-in
./install.sh
```

The installer copies the helpers to:

```text
~/.local/bin/sleep-in
~/.local/bin/sleep-in-fire
```

It also adds this binding to `~/.config/hypr/bindings.conf` when that shortcut is not already bound:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

Hyprland usually reloads automatically when config files change; the installer also attempts `hyprctl reload` when running inside Hyprland.

## Manual install

```bash
install -Dm755 bin/sleep-in ~/.local/bin/sleep-in
install -Dm755 bin/sleep-in-fire ~/.local/bin/sleep-in-fire
```

Then add this to your Hyprland bindings:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

## Requirements

- Hyprland
- Omarchy's `omarchy-menu-input`
- `systemd-run --user`
- `notify-send`
- Waybar is optional; the script ignores it if it is not running

## Why the timer fires through Hyprland

Calling `systemctl suspend` directly from a `systemd --user` timer can run outside the active desktop session. On some systems that leaves `systemctl` waiting for an invisible interactive authorization prompt, so the timer appears in Waybar but never reaches logind. `sleep-in-fire` avoids that by asking Hyprland to start the suspend command inside the active session when the timer fires.

## Cancel a scheduled suspend

The script creates transient user units named `sleep-in-<timestamp>`. You can list or cancel them with systemd:

```bash
systemctl --user list-timers 'sleep-in-*'
systemctl --user stop 'sleep-in-*.timer' 'sleep-in-*.service'
```

## License

MIT
