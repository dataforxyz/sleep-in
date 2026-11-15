# Sleep In

Small Omarchy/Hyprland helper for suspending the system after a chosen wall-clock delay.

Press `Super` + `Ctrl` + `Alt` + `S`, then enter a duration such as `90`, `30m`, `2h`, or `1h30`.

## Behavior

When a timer is scheduled, Sleep In:

1. Disables normal idle behavior through `omarchy-toggle-idle`—the same action as `Super` + `Ctrl` + `I`—so the normal idle suspend cannot happen first.
2. Creates one transient systemd user timer for the requested wall-clock deadline.
3. Restores normal idle behavior when the timer fires or is cancelled.
4. Asks Hyprland to launch a suspend helper from the graphical session, avoiding hidden authorization prompts from a background user service.
5. Checks the system journal for the actual suspend job result. Failed attempts are retried up to three times, 30 seconds apart. An unknown outcome stops retries to avoid overlapping suspend requests.

A successful Hyprland dispatch or `systemctl suspend` exit only means the request was accepted. Sleep In waits for the system suspend job to finish, which normally happens after waking. If suspend fails, it sends a persistent critical notification and saves diagnostics to `~/.local/state/sleep-in/failure` (or the corresponding `XDG_STATE_HOME` path). Click or tap the notification to copy the latest failure diagnostics to your clipboard and dismiss it; right-click dismisses without copying. The latest report is retained across cancellation and successful timers. It cannot repair a kernel or application process stuck in uninterruptible I/O.

Only one timer is active at a time. Scheduling another replaces the existing timer.
Lifecycle operations are serialized, and each timer has an identity so an old callback cannot suspend a replacement timer. Cancellation prevents further retries; a suspend request already handed to logind cannot be recalled.

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
~/.local/bin/sleep-timer-status
~/.local/bin/sleep-timer-menu
```

It also adds this binding to `~/.config/hypr/bindings.conf` if the shortcut is available:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

Hyprland usually reloads automatically after config changes; the installer also attempts a reload and reports config errors when run inside Hyprland.
The installer adds `~/.config/mako/sleep-in.conf` to Mako's configuration and reloads it to enable the persistent notification's clipboard action.

## Commands

```bash
sleep-in                  # Prompt for a delay
sleep-in schedule 1h30    # Schedule without the prompt
sleep-in status           # Print the current timer state
sleep-in cancel           # Cancel and restore normal idle behavior
sleep-in copy-failure     # Copy the latest failure report to the clipboard
```

`status` prints either `inactive` or a tab-separated line containing `scheduled`, the deadline epoch, and the requested minutes.

## Files

```text
bin/sleep-in           # timer lifecycle, idle handling, status, and suspend request
bin/sleep-in-fire      # compatibility wrapper for timers from older versions
bin/sleep-timer-status # Waybar JSON status provider
bin/sleep-timer-menu   # Waybar cancellation menu
hypr/sleep-in.conf     # Hyprland binding snippet
install.sh             # installer
```

Runtime state is stored under `${XDG_STATE_HOME:-~/.local/state}/sleep-in/`.

## Requirements

- Hyprland
- Omarchy's `omarchy-menu-input` and `omarchy-toggle-idle`
- `systemd-run --user`
- `notify-send`
- `flock` (util-linux), Python 3, and access to the system journal
- Mako and `wl-copy` (wl-clipboard) for clicking failure notifications to copy diagnostics
- Waybar is optional; Sleep In includes status/menu helpers and sends their refresh signal when available

## Manual install

```bash
install -Dm755 bin/sleep-in ~/.local/bin/sleep-in
install -Dm755 bin/sleep-in-fire ~/.local/bin/sleep-in-fire
install -Dm755 bin/sleep-timer-status ~/.local/bin/sleep-timer-status
install -Dm755 bin/sleep-timer-menu ~/.local/bin/sleep-timer-menu
```

Then add this to `~/.config/hypr/bindings.conf`:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

For notification actions, install `mako/sleep-in.conf` to `~/.config/mako/sleep-in.conf`, add `include=~/.config/mako/sleep-in.conf` to `~/.config/mako/config`, and run `makoctl reload`.

## License

MIT

## Troubleshooting and verification

```bash
journalctl --user -u sleep-in.service -u sleep-in.timer --since yesterday
journalctl -t sleep-in --since yesterday
journalctl -u systemd-suspend.service --since yesterday
journalctl -k --since yesterday --grep='Freezing|refusing|PM:'
cat ~/.local/state/sleep-in/failure
```

Run the isolated regression tests without suspending the machine:

```bash
python3 -m unittest discover -s tests -v
shellcheck bin/sleep-in bin/sleep-in-fire install.sh
```

## Omarchy Quattro

The timer reads native Stay Awake status and dispatches through the Lua Hyprland
API. It safely clears an orphaned updater sleep inhibitor only while holding the
updater lock; active updates and other applications’ inhibitors remain respected.
The cancellation menu uses `omarchy-menu-select`. Dependencies include `jq` and
Omarchy’s native menu/idle helpers.

On Quattro the installer copies the helpers and prints a Lua binding for
`~/.config/hypr/bindings.lua`; it does not install legacy Mako/Hyprland config.
For example:

```lua
o.bind("SUPER + CTRL + ALT + S", "Schedule suspend", "~/.local/bin/sleep-in")
```

The old Mako notification-action setup applies only to pre-Quattro desktops.
Quattro displays the timer’s notifications through its own shell; failure reports
can always be copied with `sleep-in copy-failure`. No actual suspend is performed
by the regression tests.
