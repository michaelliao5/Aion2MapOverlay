# AION 2 live cube map overlay

A local Windows companion that draws packet-detected cube candidates on the game's transparent map overlay. Based on hnomkeng/Aion2MapOverlay. This branch replaces static potential spawn markers with live detections and adds a tracker, spoken compass guidance, and a portable launcher.

## Run the local release

Install Npcap from its official website once. Extract the release, stop the earlier prototype tracker and overlay, then double-click Start.cmd. Keep the transparent Elyos map visible on the primary display. Stop.cmd or exiting the overlay tray menu stops the managed tracker and overlay. Python and .NET are bundled. No game input automation or packet sending.

settings.json saves voice/sound, adapter selection and world units per meter. Setting sound=false mutes both sound and voice. overlay/map-calibration.json controls world-to-map alignment. Defaults remain experimental. Raw packet-message recording is off by default; enable recordPackets only for investigation. Recordings and diagnostic logs stay in logs/; live state stays in state/. These contain game data and must not be uploaded without review. The launcher never starts with Windows automatically and does not install drivers.

## Status and limitations

The detector publishes a heartbeat every five seconds. Missing game packets hide markers after 20 seconds and are reported separately from a stopped detector. Direction/distance require a player position no older than five seconds. Only experimentally observed cube types are recognized; catalogue and packet decoding remain incomplete. Elyos map matching is supported; Asmodian candidates are excluded from this map. Multi-monitor support and exact world-to-map calibration are not yet validated. Reported meters use an estimated 100 world units per meter.

## Develop

.NET 10 SDK and Python 3.14 are used by this local build. Run python -m unittest discover -s tracker -p test_probe.py. dotnet publish -c Release -r win-x64 --self-contained true builds the overlay. Aion2MapOverlay.exe --self-test checks feed filtering/freshness and reference-map projection. --match-recording PATH checks a locally provided grayscale/colour gameplay capture without saving a new screenshot; --diagnose explicitly captures a local diagnostic image.

See scripts/build.ps1 for release assembly. See THIRD_PARTY.md before public binary releases. No raw captures, screenshots, compiled binaries or credentials belong in this repository. This is a hardened local beta, not a complete or calibrated game-world tracker.

The broad trial whitelist was disabled after noisy alerts. Live alerts use only types 1200039, 1200040, 1200041 and 1301199; the overlay filters to the three Elyos types. Unconfirmed IDs stay in offline mining reports.

Observed cube types: 1200039, 1200040, 1200041, and rift type 1301199 (not projected on this Elyos map). The 1200040 collection matched earlier cube completion/removal signatures. Trial IDs remain distinct from that evidence.

The standalone Python tracker and live overlay can be launched separately. The production launcher is optional. Recovery also handles the recorded 61-byte object frame whose complete coordinate header was swallowed by a short decoded NPC Spawn packet; missing metadata is explicitly labeled. This path still requires a configured type, nonzero entity, flags 4 and plausible coordinates.

## Mine existing recordings

Run python tracker/mine_cube_ids.py --folder PATH_TO_LOCAL_LOGS --output PATH_TO_REPORTS. The utility scans a2log captures, maps object appearances to collection signatures within each connection and zone, checks removal packets, and writes catalogue.json, encounters.csv and README.md locally. Session entity IDs are listed as evidence; reusable type IDs classify objects. It does not modify live alert settings and cannot enumerate types never sent to the client. The observed signature remains experimental. Reports and raw captures are not committed.

The local scan of 27 recordings found 32 matching completion/removal sequences spanning types 1200039, 1200040, 1200041 and 1301199. Five completion signatures had no mapped appearance; those remain unresolved.

## Transparent-map matching

Matching focuses on the bottom-right transparent map (78?99.5% of desktop width, 63?98% of desktop height), with a 16000-feature reference budget. The saved gameplay capture passed with 26 matches and 71% confidence. Marker projection adds the crop origin before converting physical screen coordinates to overlay-local WPF coordinates. Synthetic corner-map regression matched within one pixel of the expected desktop point. This checks rendering math, not the provisional game-world calibration. Keep the transparent map in its default bottom-right position.

app/overlay-status.json retains lastCandidate diagnostics after a candidate disappears, distinguishing failed matching from a projected point outside the visible map. A zero-candidate feed still draws no live rings.

Collected cubes are removed from guidance as soon as the matching completion signature arrives. Guarded inner-frame recovery also handles embedded removals/completions for tracked entities; coordinate and lifecycle frames are processed in packet order. Cube-set changes are published immediately instead of waiting for the usual state-write interval. Recorded regression tests cover the stale entity 56885 encounter.

The v2 capture backend preserves raw Player packets alongside successfully decoded events, allowing embedded cube-header recovery. The probe prefers bin/a2k-fixed-v2.exe when present. A guarded Player-header fallback requires the observed 61-byte frame prefix, configured type, flags 4, nonzero entity and valid coordinates; following metadata is explicitly treated as incomplete. Recorded replay for entity 28003 alerts on appearance and clears on collection removal. Backend tests and 31 Python tests pass. Existing running processes require a restart to load the changes.

Fresh cube detections still say ?Cube found? when player identity/position is unavailable. The unavailable-position warning is spoken once until position returns; duplicate entities remain silent. Direction and distance remain withheld until a fresh own-character position is available. Starting capture after entering a zone can miss Self identification; do not reuse an old --player-entity value across rifts or sessions. A known, user-timed interaction can identify the current actor without leaving the region.

The persistent top-left status panel is replaced by a large top-center CUBE FOUND banner. It appears only for fresh active cube detections and disappears for zero cubes, stale data or a stopped detector. It does not require successful minimap matching and also announces detected rift type 1301199. Multiple active cubes show a count. Diagnostics remain in overlay-status.json; the banner and markers remain click-through.
