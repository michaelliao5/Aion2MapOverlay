$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$cubeVoice = New-Object -ComObject SAPI.SpVoice
$cubeVoice.Rate = 0
while ($null -ne ($cubeSpeechLine = [Console]::ReadLine())) {
    if ($cubeSpeechLine.Length -gt 0) {
        # Async speech, replacing older directions rather than queueing stale advice.
        [void]$cubeVoice.Speak($cubeSpeechLine, 3)
    }
}
[void]$cubeVoice.WaitUntilDone(5000)
