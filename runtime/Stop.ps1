$stateDirectory = Join-Path $PSScriptRoot 'state'
New-Item -ItemType Directory -Force -Path $stateDirectory | Out-Null
Set-Content -LiteralPath (Join-Path $stateDirectory 'stop.flag') -Value 'stop' -Encoding ascii
