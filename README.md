# Sleep In

Small Omarchy/Hyprland helper for suspending the system after a chosen wall-clock delay.

Press `Super` + `Ctrl` + `Alt` + `S`, then enter a duration such as `90`, `30m`, `2h`, or `1h30`.

## Behavior

When a timer is scheduled, Sleep In:

1. Disables `hypridle` through `omarchy-toggle-idle`—the same action as `Super` + `Ctrl` + `I`—so the normal idle suspend cannot happen first.
2. Creates one transient systemd user timer for the requested wall-clock deadline.
3. Restores normal idle behavior when the timer fires or is cancelled.
4. Asks Hyprland to launch `systemctl --no-ask-password suspend` from the graphical session, avoiding hidden authorization prompts from a background user service.

Only one timer is active at a time. Scheduling another replaces the existing timer.

The timer uses a realtime `OnCalendar` deadline rather than a monotonic `OnActive` delay. Monotonic timers pause while the computer is suspended, which can leave an old timer pending after the computer resumes.

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

It also adds this binding to `~/.config/hypr/bindings.conf` if the shortcut is available:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

Hyprland usually reloads automatically after config changes; the installer also attempts a reload and reports config errors when run inside Hyprland.

## Commands

```bash
sleep-in                  # Prompt for a delay
sleep-in schedule 1h30    # Schedule without the prompt
sleep-in status           # Print the current timer state
sleep-in cancel           # Cancel and restore normal idle behavior
```

`status` prints either `inactive` or a tab-separated line containing `scheduled`, the deadline epoch, and the requested minutes.

## Files

```text
bin/sleep-in          # timer lifecycle, idle handling, status, and suspend request
bin/sleep-in-fire     # compatibility wrapper for timers from older versions
hypr/sleep-in.conf    # Hyprland binding snippet
install.sh            # installer
```

Runtime state is stored under `${XDG_STATE_HOME:-~/.local/state}/sleep-in/`.

## Requirements

- Hyprland
- Omarchy's `omarchy-menu-input` and `omarchy-toggle-idle`
- `systemd-run --user`
- `notify-send`
- Waybar is optional; Sleep In sends its refresh signal when available

## Manual install

```bash
install -Dm755 bin/sleep-in ~/.local/bin/sleep-in
install -Dm755 bin/sleep-in-fire ~/.local/bin/sleep-in-fire
```

Then add this to `~/.config/hypr/bindings.conf`:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

## License

MIT
