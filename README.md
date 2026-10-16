# AION 2 Cube Tracker + Map Overlay

A Windows companion that alerts you to recognized nearby cube candidates with a large **CUBE FOUND** banner, sound, and spoken compass guidance. It can also draw live markers on the game's transparent Elyos map.

## Download and play

1. Install [Npcap](https://npcap.com/#download) once.
2. [Download the Windows ZIP](https://github.com/michaelliao5/Aion2MapOverlay/releases/download/v0.2.0/Aion2CubeTracker-0.2.0-win-x64.zip) and **Extract All**.
3. Close older tracker/overlay instances. Double-click **Start.cmd**, then enter the game world. Both the detector and overlay start together.
4. Double-click **Stop.cmd** when finished.

Python and .NET are bundled. You do not need a terminal or separate relay commands. The overlay stays invisible until a cube is detected. Keep the transparent Elyos map in its normal bottom-right position on your primary screen for map markers.

**[Read the step-by-step user guide](USER_GUIDE.md)** for installation, what alerts mean, sound settings, troubleshooting and updates. [All releases](https://github.com/michaelliao5/Aion2MapOverlay/releases).

## What to expect

The banner and sound work independently of map matching. Direction and estimated distance need a fresh player position. Collection/removal clears detected cubes when the corresponding event is received. Stopped capture or stale traffic hides the display.

This is experimental: only observed cube types are recognized, and some cubes may be missed. Rift detections show the banner but do not project onto the Elyos map. Map alignment and meter scale are provisional; multiple monitors have not been validated.

Edit **settings.json** while stopped to configure sound and voice. Raw game-message recording is off by default. Logs stay in **logs/**; live state stays in **state/**. Do not publish recordings or personal game data.

## For developers

Use Windows x64, .NET 10 SDK, Python 3.14 and `tracker/requirements-build.txt`. Build the capture backend using the pinned revision and patch in [THIRD_PARTY.md](THIRD_PARTY.md), then run:

```powershell
./scripts/build.ps1 -BackendPath C:/path/to/a2k-fixed-v2.exe
```

The build runs Python regressions, overlay projection/feed self-tests, six tracker-to-overlay integration checks, and launcher validation. To check the state-file protocol and actual banner logic without showing synthetic cubes on your desktop:

```powershell
python scripts/check-integration.py C:/path/to/Aion2MapOverlay.exe
```

The Python tracker and overlay can run separately for development. Pass the same absolute path to tracker `--map-state` and overlay `--state`. The launcher owns only processes it starts and does not install drivers or start with Windows.

Offline mining: `python tracker/mine_cube_ids.py --folder PATH_TO_LOGS --output PATH_TO_REPORTS`. This finds observed types in recordings, not a complete game catalogue. Never commit captures, screenshots, credentials or generated state.

Based on [hnomkeng/Aion2MapOverlay](https://github.com/hnomkeng/Aion2MapOverlay). See [THIRD_PARTY.md](THIRD_PARTY.md) for attribution and licensing details.
