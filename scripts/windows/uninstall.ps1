$ErrorActionPreference = 'Stop'
$AppRoot = Join-Path $env:LOCALAPPDATA 'RadarInvestimentos'
$Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$TaskName = 'RadarInvestimentos-' + $Identity.User.Value
$StartupLink = Join-Path ([Environment]::GetFolderPath('Startup')) 'RadarInvestimentos.lnk'
try {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    if (Test-Path -LiteralPath $StartupLink) { Remove-Item -LiteralPath $StartupLink }
    $Worker = Join-Path $AppRoot 'scripts\windows\worker.py'
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($Worker) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Write-Host 'Inicializacao automatica removida. Configuracao, relatorios e historico foram preservados.'
    Write-Host ('Pasta: ' + $AppRoot)
    exit 0
} catch {
    Write-Host 'Nao foi possivel remover a tarefa. Abra o Agendador de Tarefas e procure RadarInvestimentos.'
    exit 1
}
