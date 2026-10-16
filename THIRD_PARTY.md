# Third-party provenance

Overlay base: https://github.com/hnomkeng/Aion2MapOverlay at 3b6086ff1a39bbd12c76a7ce7a9016d3a1cee63c. No license file was found in that revision; do not assume permission for commercial redistribution.

Map assets/data are credited upstream to Yihao Liu and https://github.com/aion2-interactive-map/aion2-interactive-map. The reference data identifies CC BY-NC 4.0; artwork belongs to NCSOFT. Review asset and upstream licensing before public binary distribution.

Packet backend: https://github.com/nuriland/a2kit at 13a058e683ec7bdf9d0a8b0603233a2ed1e1b95b, MIT. Apply third-party/npcap-source.patch, then build on Windows with CGO_ENABLED=0 and go build -tags npcap -o a2k-fixed.exe ./cmd/a2k. Dependency notices are in third-party/LICENSE.*. Npcap is installed separately from https://npcap.com/ and is not redistributed.

The portable tracker is built using PyInstaller. Python and PyInstaller runtime notices are included in licenses/ in the portable release. WPF/OpenCvSharp/YamlDotNet dependencies are pinned in the project file. OpenCvSharp and OpenCV use Apache-2.0; YamlDotNet and its libyaml-derived code use the included MIT notices. Copies are in third-party/LICENSE.* and in the portable bundle. OpenCvSharp license text was obtained from its upstream master LICENSE; OpenCV from tag 4.10.0; YamlDotNet from tag v16.2.1. No blanket license is asserted over the upstream overlay or game assets.
