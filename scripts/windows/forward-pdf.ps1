$ErrorActionPreference = 'Stop'
$AppRoot = Join-Path $env:LOCALAPPDATA 'RadarInvestimentos'
$Python = Join-Path $AppRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Execute INSTALAR_WINDOWS.cmd primeiro.' }
Add-Type -AssemblyName System.Windows.Forms
$Dialog = New-Object System.Windows.Forms.OpenFileDialog
$Dialog.Filter = 'Relatorio PDF (*.pdf)|*.pdf'
$Dialog.Title = 'Selecione o PDF exportado manualmente do ChatGPT'
if ($Dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Set-Location -LiteralPath $AppRoot
    & $Python -m radar.cli forward $Dialog.FileName
    if ($LASTEXITCODE -ne 0) { throw 'Encaminhamento interrompido. Verifique o arquivo e o estado de envio.' }
}
