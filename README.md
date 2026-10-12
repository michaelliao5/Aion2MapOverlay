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

The user-enabled trial whitelist covers 1200000 through 1200099 inclusive. Aside from observed cube types 1200039, 1200040 and 1200041, these types are unconfirmed and can produce non-cube alerts.

Observed cube types: 1200039, 1200040, 1200041, and rift type 1301199 (not projected on this Elyos map). The 1200040 collection matched earlier cube completion/removal signatures. Trial IDs remain distinct from that evidence.

The standalone Python tracker and live overlay can be launched separately. The production launcher is optional. Recovery also handles the recorded 61-byte object frame whose complete coordinate header was swallowed by a short decoded NPC Spawn packet; missing metadata is explicitly labeled. This path still requires a configured type, nonzero entity, flags 4 and plausible coordinates.
