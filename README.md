# Browsy

A keyboard-first plugin browser for Ableton Live. Connects via a Remote Script, scans all your VST3, VST2, AU and Max for Live devices, and lets you load them on the selected track without touching the mouse.

---

## Setup

1. Install the app from the `.dmg`
2. Open Browsy and click **?** — it will guide you through the full setup

---

## Features

**Instant loading**
Select a plugin and press `Enter` to load it on the selected Ableton track. Double-click to load in one move. Browsy switches focus back to Ableton automatically.

**Search**
Type any part of a name or vendor — results are ranked by closeness. Filter by category (Audio FX, Instruments, MIDI FX, M4L) and format (VST3, VST2, AU). Press `Esc` to clear.

**Shortcuts**
Right-click any plugin → Assign to slot to pin it to one of 6 shortcut slots. Press the matching key to load instantly — works even when Ableton is in focus.
- AZERTY: `& é " ' ( -`
- QWERTY: `1 2 3 4 5 6`

Press `Cmd+Shift+F` in Ableton to bring Browsy to the front.

**Tags**
Right-click any plugin → Edit Tags to organise your library. Filter by tag from the search bar using `#tag`. Stack multiple tags and mix with text search.

**AI tagging**
Export your full plugin list from Settings → Export for AI. Feed the JSON to any AI assistant to tag your whole library at once, then import the result back.

**Scan cache**
Plugin list is cached locally — Browsy loads instantly on every startup without rescanning. Rescan manually from Settings.

---

## Files

| File | Description |
|------|-------------|
| `main.js` | Electron main process |
| `preload.js` | Context bridge |
| `browsy.html` | UI and app logic |
| `plugin-tags.js` | Default tag database |
| `remote-script/Browsy/` | Ableton Remote Script |

---

## OSC

Browsy listens on port **11001**, sends to Ableton on port **11000**.

| Address | Description |
|---------|-------------|
| `/shortcut n` | Trigger shortcut slot n (1–6) |
| `/browsy/focus` | Bring Browsy window to front |

---

## Requirements

- macOS
- Ableton Live 11 or later
- Max for Live (only if scanning `.amxd` files)
