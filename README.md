# AION 2 live cube tracker + map overlay

Portable Windows x64 companion with packet-based cube detection, a top-center **CUBE FOUND** banner, Windows sound, spoken compass guidance, and live markers on the transparent Elyos map.

## Start

1. Install [Npcap](https://npcap.com/) once.
2. Download the ZIP from [Releases](https://github.com/michaelliao5/Aion2MapOverlay/releases) and extract it to a writable folder.
3. Stop any older tracker/overlay, then double-click **Start.cmd**. It starts both programs and connects them automatically. Python and .NET are included.
4. Start capture before entering the game world so player identity can be detected. Keep the game's transparent map in its default bottom-right position on the primary display for map markers.
5. Double-click **Stop.cmd** to stop both, or exit through the overlay tray menu.

The display stays empty when there are no active cubes. The banner appears without a map match and disappears on collection, removal, stopped capture, or stale game traffic. Map markers additionally require a successful map match. No separate relay command is needed in this package.

## Settings and troubleshooting

Edit `settings.json` while stopped. `sound=false` mutes sound and voice; `voice=false` keeps only the chime. Adapter selection is automatic unless `adapter` is specified. `unitsPerMeter` defaults to the estimated value 100. Raw game-message recording is disabled by default; enable `recordPackets` for investigating missed detections.

The shared feed is `state/cube_state.json`; diagnostics are `overlay/overlay-status.json` and `logs/`. Keep captures and diagnostic data private. If there is no detection, inspect the tracker logs for recognized game traffic. If sound works but no map marker appears, inspect map matching diagnostics and keep the transparent map in its default location. A missing player position prevents direction/distance, but does not suppress a fresh cube announcement. Restart capture before entering the world rather than reusing an entity override from another session or zone.

Recognized observed types are 1200039, 1200040, 1200041 and rift type 1301199. Only the three Elyos types project onto the Elyos map; rift detections still show the banner. The catalogue and protocol decoding are incomplete. World-to-map calibration and distance scale are provisional. Exact marker alignment and multiple monitors have not been validated. This is an experimental companion, with no guarantee of detecting every cube.

## Build and verify

Use Windows x64, .NET 10 SDK, Python 3.14 and the pinned `tracker/requirements-build.txt`. Build the Npcap backend from the revision and patch in [THIRD_PARTY.md](THIRD_PARTY.md). Then run:

```powershell
./scripts/build.ps1 -BackendPath C:/path/to/a2k-fixed-v2.exe
```

The build runs Python regressions, overlay projection/feed self-tests, tracker-to-overlay integration checks, and launcher validation. `scripts/check-integration.py PATH_TO_OVERLAY_EXE` checks the actual state-file protocol and banner for empty, detected, collected, rift, stale and stopped states without showing synthetic cubes on your desktop.

For development, the Python tracker and overlay can still run separately; pass the same absolute state path using tracker `--map-state` and overlay `--state`. The launcher owns only the processes it starts and does not install drivers or start with Windows.

Offline mining: `python tracker/mine_cube_ids.py --folder PATH_TO_LOGS --output PATH_TO_REPORTS`. This finds observed types from existing captures, not a complete game catalogue. Do not commit recordings, screenshots, credentials or generated state.

Based on [hnomkeng/Aion2MapOverlay](https://github.com/hnomkeng/Aion2MapOverlay). Third-party attribution and licensing details are in [THIRD_PARTY.md](THIRD_PARTY.md).
