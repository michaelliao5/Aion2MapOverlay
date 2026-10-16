# How to use the AION 2 Cube Tracker

This app watches the game traffic your PC receives and alerts you when it recognizes a nearby cube. It starts the detector and map overlay together. You do not need Python, a terminal, or separate relay commands.

## 1. Download and install

You need a Windows 64-bit PC running AION 2.

1. Install [Npcap from its official website](https://npcap.com/#download). This is the capture driver the tracker needs. The tracker ZIP does not include it.
2. Open the [v0.2.0 download page](https://github.com/michaelliao5/Aion2MapOverlay/releases/tag/v0.2.0).
3. Under **Assets**, download **Aion2CubeTracker-0.2.0-win-x64.zip**. The **Source code** downloads are for developers; choose the named tracker ZIP to run the app.
4. Right-click the ZIP in File Explorer and choose **Extract All**. Choose a folder you can write to, such as a folder inside Documents.
5. Open the extracted folder. You should see **Start.cmd**, **Stop.cmd**, **settings.json**, **tracker**, and **overlay** together. Keep them together. Do not run the app from inside the ZIP.

[Download the Windows ZIP directly](https://github.com/michaelliao5/Aion2MapOverlay/releases/download/v0.2.0/Aion2CubeTracker-0.2.0-win-x64.zip)

## 2. Start a session

1. Close any older cube tracker or overlay you already have running.
2. Double-click **Start.cmd** in the extracted folder. It starts both parts in the background.
3. Start AION 2 and enter the game world. Starting the tracker before entering the world gives it a chance to identify your character for spoken direction and distance.
4. For map markers, display the game's transparent Elyos map in its usual bottom-right position on your primary screen.
5. Play normally. An empty screen is expected when no cube is detected. There is no permanent top-left status panel.

You do not need to start the tracker executable, a Python script, or a relay separately. Double-clicking Start again while this launcher is running does not start a second managed session.

## 3. What you will see and hear

| What happens | What the app does |
| --- | --- |
| A recognized cube appears in received game traffic | Shows a large **CUBE FOUND** banner at the top center and plays a chime and voice, if enabled. |
| Your character's current position is available | Can speak a compass direction and estimated distance. |
| Your position is unavailable | Still announces a fresh cube; direction and distance are unavailable. |
| The transparent Elyos map is successfully matched | Can draw a live cube marker on the map. |
| A cube is collected or removed and that event is received | Clears that cube from the active display. |
| No cubes remain, capture stops, or game traffic becomes stale | Hides the banner and markers. |

The banner does not require the map to match. An alert without a map marker can therefore be normal. An alert means the client received a recognized cube candidate; it does not guarantee the cube is still available when you reach it.

## 4. Stop

Double-click **Stop.cmd** in the same extracted folder. It stops the detector and overlay together. You can also exit through the overlay's system-tray menu; look in the hidden tray icons near the Windows clock if needed.

Use Stop before changing settings, moving the folder, or installing an update. The app does not automatically start with Windows.

## 5. Change sound or other settings

Stop the app first. Right-click **settings.json**, open it with Notepad, edit it, save, and start again. Keep the commas, quotes and braces as shown. Use lowercase `true` and `false` without quotes.

Default settings:

```json
{
  "voice": true,
  "sound": true,
  "adapter": "",
  "unitsPerMeter": 100,
  "recordPackets": false
}
```

| Setting | What to use |
| --- | --- |
| `voice` | `true` for spoken alerts. Set to `false` for chime only. |
| `sound` | `false` silences both the chime and voice. Visual alerts still work. |
| `adapter` | Leave `""` for automatic network adapter selection. This is an advanced setting. |
| `unitsPerMeter` | Leave at `100` unless you have measured a better scale. Distances are estimates. |
| `recordPackets` | Leave `false` for normal play. Set to `true` temporarily when investigating a missed detection. Recordings can grow large. |

To use only a chime, set `voice` to `false` and keep `sound` as `true`. To use only the visual display, set `sound` to `false`.

## 6. If something does not work

### Nothing is visible after Start

The overlay is intentionally invisible when there are no active cubes. This alone does not mean it failed. Open the **logs** folder in the extracted app folder and look at the newest **tracker-...log** in Notepad. The line **GAME PROTOCOL MESSAGE RECEIVED** means it has recognized game traffic. It does not prove that every cube can be detected.

If a startup error window appears, follow its message. If it says Npcap is required, install Npcap and try again. Check that you extracted the full ZIP and kept all its folders together.

### I hear a cube, but no marker appears on the map

The banner and sound can work independently of map matching. Keep the transparent Elyos map in its default bottom-right position on the primary display. Map markers currently support Elyos cube types only. Exact marker alignment is still experimental.

For more detail, open **overlay/overlay-status.json** in Notepad. It contains map matching and active-cube diagnostics; you do not need to edit it.

### It says position tracking is unavailable

The app may have started after the game sent your character identity, or your position may no longer be fresh. Stop it, start it again, and then re-enter the game world so it can receive your identity. Cube alerts can still work without direction or distance. Do not carry a manual player entity ID across sessions or rifts.

### No sound

Check Windows volume and the app's `sound` and `voice` settings. Restart the app after editing settings. A cube already tracked in the current session does not repeatedly trigger a new appearance alert.

### It missed a cube

Not every cube type or packet pattern is supported. If you want to investigate, stop the app, set `recordPackets` to `true`, restart it, and note the exact local time, map, and whether you opened the cube. Stop afterward and turn recording off again.

Recordings are saved in **logs**. They contain game data; do not post them publicly. A useful [GitHub issue](https://github.com/michaelliao5/Aion2MapOverlay/issues) includes the app version, map, time and timezone, what you expected, what happened, and relevant error text with personal details removed. A recording is not required to report a problem.

### Stop did not seem to work

Use **Stop.cmd** from the folder you launched. A separately launched older Python tracker or overlay is not managed by this package; close that older instance in its own console or tray menu.

## 7. Update to a new version

Stop the old version, extract the new release into a new folder, and use its Start.cmd. Reapply your preferred settings to the new settings.json. Keep the previous folder until you are happy with the update. Avoid copying old executables into the new package.

## Current limits

- This is an experimental detector, not a complete cube catalogue. It recognizes observed types 1200039, 1200040, 1200041 and rift type 1301199.
- Rift detections can show the banner, but are not projected onto the Elyos map.
- Detection depends on game traffic received by your client. No fixed detection radius has been established.
- Compass guidance needs a fresh player position. Meter scale and world-to-map alignment are provisional.
- Multiple monitors and exact marker alignment have not been validated.

The package captures received traffic; it does not send game packets or automate game input. Third-party attribution is in **THIRD_PARTY.md** in the download and repository.
