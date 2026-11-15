# Sleep In

Small Omarchy/Hyprland helper for suspending the system after a chosen wall-clock delay.

On Omarchy Quattro, press the configured Sleep In shortcut and enter a duration
such as `90`, `30m`, `2h`, or `1h30`. The example binding below uses
`Super` + `Ctrl` + `Alt` + `S`; keep your own existing shortcut if you use a
different one.

`main` targets Quattro. The previous upstream main is preserved at
[`archive/pre-quattro-20261115`](https://github.com/dataforxyz/sleep-in/tree/archive/pre-quattro-20261115)
for historical reference; it is not a separately maintained legacy release.

## Behavior

When a timer is scheduled, Sleep In:

1. Temporarily disables normal idle behavior, remembering whether it was enabled before the timer. On Quattro it reads the native Stay Awake state and uses Omarchy’s idle helper; on older Hyprland installs it uses the `hypridle` process fallback.
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

On older Hyprland/Waybar installs, it can add this binding to `~/.config/hypr/bindings.conf` if the shortcut is available:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

On pre-Quattro Hyprland, the installer attempts a reload and reports config errors when run inside Hyprland. It adds `~/.config/mako/sleep-in.conf` to Mako's configuration for the persistent notification's clipboard action.

On Quattro, the installer detects `~/.config/hypr/hyprland.lua`, copies the
helpers, and prints a Lua binding example for `~/.config/hypr/bindings.lua`.
Add it there only if you want that key and it is available. The installer leaves
Quattro's Lua bindings and shell notifications alone; it does not configure the
Omarchy bar automatically.

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
- Omarchy's `omarchy-menu-input` and `omarchy-toggle-idle`; Quattro also uses `omarchy-menu-select`, `jq`, and the installed native idle service
- `systemd-run --user`
- `notify-send`
- `flock` (util-linux), Python 3, and access to the system journal
- `wl-copy` (wl-clipboard) for copying failure diagnostics
- On pre-Quattro installs, Mako enables click-to-copy notification actions. Quattro uses its native shell notifications; run `sleep-in copy-failure` to copy a report.
- Waybar is optional. `sleep-timer-status` and `sleep-timer-menu` expose Waybar modules; Quattro's native bar integration is a user shell configuration and is not installed by this tool.

## Manual install

```bash
install -Dm755 bin/sleep-in ~/.local/bin/sleep-in
install -Dm755 bin/sleep-in-fire ~/.local/bin/sleep-in-fire
install -Dm755 bin/sleep-timer-status ~/.local/bin/sleep-timer-status
install -Dm755 bin/sleep-timer-menu ~/.local/bin/sleep-timer-menu
```

For pre-Quattro Hyprland, add this to `~/.config/hypr/bindings.conf`:

```conf
bindd = SUPER CTRL ALT, S, Schedule suspend, exec, ~/.local/bin/sleep-in
```

For pre-Quattro Mako notification actions, install `mako/sleep-in.conf` to `~/.config/mako/sleep-in.conf`, add `include=~/.config/mako/sleep-in.conf` to `~/.config/mako/config`, and run `makoctl reload`. On Quattro, use the Lua binding example above and native shell notifications; do not add the Mako include or legacy `bindings.conf` snippet.

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

## Omarchy Quattro details

The suspend request uses Quattro's Lua Hyprland dispatcher. Before requesting
suspend, Sleep In checks for an orphaned Omarchy updater inhibitor and only asks
the updater's lock-protected cleanup helper to release it. If an update is
active or safe cleanup fails, the timer defers suspend. Other applications'
inhibitors remain in force and are included in failure diagnostics. This is a
mechanism description; actual suspend/resume still depends on the hardware,
kernel, and applications.

The cancellation menu uses `omarchy-menu-select`. The repository's
`sleep-timer-status` and `sleep-timer-menu` scripts target Waybar. If you want
the timer displayed in Omarchy's native bar, configure it in your own shell
layout; the helper installer does not add or remove bar widgets. The private
Quattro desktop configuration snapshot documents Ben's personal integration.

Example Lua binding, if this key is available on your setup:

```lua
o.bind("SUPER + CTRL + ALT + S", "Schedule suspend", "~/.local/bin/sleep-in")
```

The old Mako notification-action and `bindings.conf` steps above apply only to
pre-Quattro desktops. Quattro displays notifications through its shell; copy a
saved failure report with `sleep-in copy-failure`. The regression tests use
harmless stubs and do not perform an actual suspend.
