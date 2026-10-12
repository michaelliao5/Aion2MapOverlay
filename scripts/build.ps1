param([string]$BackendPath, [string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $sourceRoot 'artifacts\release' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$overlayOutput = Join-Path $OutputDirectory 'overlay'
$trackerOutput = Join-Path $OutputDirectory 'tracker'
New-Item -ItemType Directory -Force -Path $overlayOutput,$trackerOutput | Out-Null
python -m unittest discover -s (Join-Path $sourceRoot 'tracker') -p test_probe.py
if ($LASTEXITCODE -ne 0) { throw 'Tracker tests failed.' }
dotnet publish (Join-Path $sourceRoot 'Aion2MapOverlay.csproj') -c Release -r win-x64 --self-contained true -o $overlayOutput
if ($LASTEXITCODE -ne 0) { throw 'Overlay build failed.' }
# Install the pinned build dependency in a dedicated environment first:
# python -m pip install pyinstaller==6.22.3
python -m PyInstaller --onefile --console --name cube-tracker --distpath $trackerOutput --workpath (Join-Path $sourceRoot 'artifacts\freeze') --specpath (Join-Path $sourceRoot 'artifacts') --noconfirm (Join-Path $sourceRoot 'tracker\cube_probe.py')
if ($LASTEXITCODE -ne 0) { throw 'Tracker freeze failed.' }
if (-not $BackendPath -or -not (Test-Path -LiteralPath $BackendPath)) { throw 'Provide -BackendPath pointing to the pinned a2kit Npcap build described in THIRD_PARTY.md.' }
New-Item -ItemType Directory -Force -Path (Join-Path $trackerOutput 'bin') | Out-Null
Copy-Item -LiteralPath $BackendPath -Destination (Join-Path $trackerOutput 'bin\a2k-fixed.exe')
Copy-Item (Join-Path $sourceRoot 'tracker\cube_ids.json'),(Join-Path $sourceRoot 'tracker\speak.ps1') $trackerOutput
Copy-Item (Join-Path $sourceRoot 'third-party\LICENSE.*') (Join-Path $trackerOutput 'bin')
Copy-Item (Join-Path $sourceRoot 'runtime\*') $OutputDirectory
Copy-Item (Join-Path $sourceRoot 'map-calibration.json') $overlayOutput
Copy-Item (Join-Path $sourceRoot 'README.md'),(Join-Path $sourceRoot 'THIRD_PARTY.md') $OutputDirectory
$check = Start-Process -FilePath (Join-Path $overlayOutput 'Aion2MapOverlay.exe') -ArgumentList '--self-test' -PassThru -WindowStyle Hidden
$check.WaitForExit()
if ($check.ExitCode -ne 0) { throw 'Overlay self-test failed.' }
& (Join-Path $OutputDirectory 'Start.ps1') -ValidateOnly
Write-Output "Local release ready: $OutputDirectory. Include Python and PyInstaller runtime notices before redistribution."
