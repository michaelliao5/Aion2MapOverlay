param([switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
$runtimeRoot = $PSScriptRoot
$stateDirectory = Join-Path $runtimeRoot 'state'
$logsDirectory = Join-Path $runtimeRoot 'logs'
$trackerExecutable = Join-Path $runtimeRoot 'tracker\cube-tracker.exe'
$overlayExecutable = Join-Path $runtimeRoot 'overlay\Aion2MapOverlay.exe'
foreach ($requiredFile in @($trackerExecutable,$overlayExecutable,(Join-Path $runtimeRoot 'settings.json'))) {
    if (-not (Test-Path -LiteralPath $requiredFile)) { throw "Missing release file: $requiredFile" }
}
$settings = Get-Content -LiteralPath (Join-Path $runtimeRoot 'settings.json') -Raw | ConvertFrom-Json
if ($settings.voice -isnot [bool] -or $settings.sound -isnot [bool] -or $settings.recordPackets -isnot [bool]) { throw 'voice and sound settings must be true or false.' }
$unitScale = [double]$settings.unitsPerMeter
if ([double]::IsNaN($unitScale) -or [double]::IsInfinity($unitScale) -or $unitScale -le 0) { throw 'unitsPerMeter must be positive and finite.' }
if ($ValidateOnly) { Write-Output 'Release files and settings validated.'; return }
if (-not (Test-Path -LiteralPath "$env:WINDIR\System32\Npcap\wpcap.dll")) { throw 'Npcap is required. Install it from https://npcap.com/ then start again.' }
New-Item -ItemType Directory -Force -Path $stateDirectory,$logsDirectory | Out-Null
$mutexName = 'Local\Aion2LiveCubeTracker'
$runMutex = New-Object System.Threading.Mutex($false,$mutexName)
$ownsMutex = $false
$trackerProcess = $null
$overlayProcess = $null
$stopFile = Join-Path $stateDirectory 'stop.flag'
try {
    try { $ownsMutex = $runMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) { return }
    if (Test-Path -LiteralPath $stopFile) { Remove-Item -LiteralPath $stopFile }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stateFile = Join-Path $stateDirectory 'cube_state.json'
    $recording = Join-Path $logsDirectory "capture-$stamp.a2log.jsonl"
    $trackerArguments = @('--log',('"'+$recording+'"'),'--map-state',('"'+$stateFile+'"'),'--stop-file',('"'+$stopFile+'"'),'--units-per-meter',$unitScale.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    if (-not $settings.recordPackets) { $trackerArguments += '--no-record' }
    if (-not $settings.sound) { $trackerArguments += '--mute' }
    elseif (-not $settings.voice) { $trackerArguments += '--no-voice' }
    if ($settings.adapter) {
        if ($settings.adapter -match '["\r\n]') { throw 'Invalid adapter setting.' }
        $trackerArguments += @('--adapter',('"'+$settings.adapter+'"'))
    }
    $trackerProcess = Start-Process -FilePath $trackerExecutable -ArgumentList $trackerArguments -WorkingDirectory (Split-Path $trackerExecutable) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDirectory "tracker-$stamp.log") -RedirectStandardError (Join-Path $logsDirectory "tracker-$stamp.err.log")
    $overlayProcess = Start-Process -FilePath $overlayExecutable -ArgumentList @('--state',('"'+$stateFile+'"')) -WorkingDirectory (Split-Path $overlayExecutable) -WindowStyle Hidden -PassThru
    while (-not $trackerProcess.HasExited -and -not $overlayProcess.HasExited -and -not (Test-Path -LiteralPath $stopFile)) {
        Start-Sleep -Seconds 1
        $trackerProcess.Refresh(); $overlayProcess.Refresh()
    }
    if ($trackerProcess.HasExited -and $trackerProcess.ExitCode -ne 0 -and -not (Test-Path -LiteralPath $stopFile)) { throw "Tracker exited with code $($trackerProcess.ExitCode). See logs\tracker-$stamp.err.log." }
    if ($overlayProcess.HasExited -and $overlayProcess.ExitCode -ne 0 -and -not (Test-Path -LiteralPath $stopFile)) { throw "Overlay exited with code $($overlayProcess.ExitCode). See overlay diagnostics." }
} finally {
    if ($ownsMutex) {
        Set-Content -LiteralPath $stopFile -Value 'stop' -Encoding ascii
        if ($trackerProcess -and -not $trackerProcess.HasExited) {
            if (-not $trackerProcess.WaitForExit(15000)) { $trackerProcess.Kill() }
        }
        if ($overlayProcess -and -not $overlayProcess.HasExited) { $overlayProcess.Kill() }
        $runMutex.ReleaseMutex()
    }
    $runMutex.Dispose()
}
