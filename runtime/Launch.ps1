$ErrorActionPreference = 'Stop'
try {
    & (Join-Path $PSScriptRoot 'Start.ps1')
} catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($_.Exception.Message, 'Cube tracker could not start') | Out-Null
}
