param([ValidateSet('Codex','ChatGPT')][string]$Mode = 'Codex')
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$AppRoot = Join-Path $env:LOCALAPPDATA 'RadarInvestimentos'
$Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$TaskName = 'RadarInvestimentos-' + $Identity.User.Value
$StartupLink = Join-Path ([Environment]::GetFolderPath('Startup')) 'RadarInvestimentos.lnk'

function Find-RadarPython {
    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe')
    )
    $Launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($Launcher) {
        foreach ($Version in @('-3.12', '-3.13', '-3.14', '-3')) {
            try {
                $Found = & $Launcher.Source $Version -c "import sys; print(sys.executable if sys.version_info >= (3,12) else '')" 2>$null
                if ($LASTEXITCODE -eq 0 -and $Found -and (Test-Path -LiteralPath $Found)) { return [string]$Found }
            } catch { continue }
        }
    }
    $OnPath = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($OnPath -and $OnPath.Source -notlike '*\WindowsApps\*') { $Candidates += $OnPath.Source }
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate) {
            & $Candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $Candidate }
        }
    }
    return $null
}

try {
    Write-Host 'Instalando Radar de Investimentos para o usuario atual...'
    New-Item -ItemType Directory -Path $AppRoot -Force | Out-Null

    # Restrict the local configuration, database and logs to the current user.
    & icacls.exe $AppRoot /inheritance:r /grant:r ('*' + $Identity.User.Value + ':(OI)(CI)F') '*S-1-5-18:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel proteger a pasta local do radar.' }

    # Stop only this application's previous installations before updating its files.
    $Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Existing) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Disable-ScheduledTask -TaskName $TaskName | Out-Null
    }
    if (Test-Path -LiteralPath $StartupLink) { Remove-Item -LiteralPath $StartupLink }
    $OldWorker = Join-Path $AppRoot 'scripts\windows\worker.py'
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($OldWorker) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }

    if ($SourceRoot -ne $AppRoot) {
        foreach ($Name in @('radar','config','scripts','docs')) {
            Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination $AppRoot -Recurse -Force
        }
        foreach ($Name in @('pyproject.toml','requirements.lock','requirements.txt','README.md','INSTALAR_WINDOWS.cmd','EXECUTAR_AGORA.cmd','DESINSTALAR_WINDOWS.cmd','ENCAMINHAR_PDF.cmd','INSTALAR_CHATGPT_MANUAL.cmd')) {
            Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination $AppRoot -Force
        }
        foreach ($Name in @('.env','.env.example')) {
            $Target = Join-Path $AppRoot $Name
            if (-not (Test-Path -LiteralPath $Target) -and (Test-Path -LiteralPath (Join-Path $SourceRoot $Name))) {
                Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination $Target
            }
        }
        $StateDir = Join-Path $AppRoot 'data'
        New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
        $SourceDB = Join-Path $SourceRoot 'data\radar.sqlite3'
        $TargetDB = Join-Path $StateDir 'radar.sqlite3'
        if ((Test-Path -LiteralPath $SourceDB) -and -not (Test-Path -LiteralPath $TargetDB)) {
            Copy-Item -LiteralPath $SourceDB -Destination $TargetDB
        }
    }
    Set-Location -LiteralPath $AppRoot
    $Python = Find-RadarPython
    if (-not $Python) {
        $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $Winget) { throw 'Instale Python 3.12 de https://www.python.org/downloads/windows/ e execute este instalador novamente.' }
        Write-Host 'Instalando Python 3.12 para o usuario atual...'
        & $Winget.Source install --id Python.Python.3.12 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar Python. Instale Python 3.12 e execute novamente.' }
        $Python = Find-RadarPython
        if (-not $Python) { throw 'Python nao localizado. Abra um novo CMD e execute o instalador novamente.' }
    }
    $VenvPython = Join-Path $AppRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        & $Python -m venv (Join-Path $AppRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python.' }
    }
    Write-Host 'Instalando dependencias verificadas...'
    & $VenvPython -m pip install --disable-pip-version-check --require-hashes -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Falha nas dependencias. Verifique a internet e execute novamente.' }
    & $VenvPython -m pip install --disable-pip-version-check --no-deps -e .
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o radar.' }

    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        Start-Process notepad.exe -ArgumentList ('"' + (Join-Path $AppRoot '.env') + '"') -Wait
    }
    & $VenvPython -c "from radar.config import Settings,Watchlist; s=Settings.from_env(); Watchlist.load(s.config_path); missing=[n for n,v in (('TELEGRAM_BOT_TOKEN',s.telegram_token),('TELEGRAM_CHAT_ID',s.telegram_chat)) if not v.get_secret_value()]; assert not missing, 'Configuracao incompleta: '+', '.join(missing); import radar.scheduler"
    if ($LASTEXITCODE -ne 0) { throw 'Configuracao incompleta. Preencha o arquivo .env na pasta do radar e execute novamente.' }

    # Migrate only the selected engine; preserve Telegram configuration and historical data.
    $SelectedProvider = if ($Mode -eq 'ChatGPT') { 'none' } else { 'codex' }
    & $VenvPython -c "from pathlib import Path; import re,sys; p=Path('.env'); s=p.read_text(encoding='utf-8-sig'); line='RESEARCH_PROVIDER='+sys.argv[1]; s=re.sub(r'^RESEARCH_PROVIDER=.*$', line, s, flags=re.M) if re.search(r'^RESEARCH_PROVIDER=',s,flags=re.M) else s+'\n'+line+'\n'; p.write_text(s,encoding='utf-8')" $SelectedProvider
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao selecionar o provedor Codex.' }
    $env:RESEARCH_PROVIDER = $SelectedProvider
    if ($Mode -eq 'ChatGPT') {
        Write-Host 'Encaminhamento manual instalado. Nenhuma tarefa diaria local foi ativada.'
        Write-Host 'Crie a tarefa na interface ChatGPT usando docs\tarefa-chatgpt.md.'
        Write-Host 'Exporte o PDF no ChatGPT e use ENCAMINHAR_PDF.cmd.'
        exit 0
    }
    & (Join-Path $AppRoot 'scripts\windows\setup-codex.ps1')

    $Worker = Join-Path $AppRoot 'scripts\windows\worker.py'
    $PythonW = Join-Path $AppRoot '.venv\Scripts\pythonw.exe'
    $WorkerArgs = '"' + $Worker + '"'
    try {
        $Action = New-ScheduledTaskAction -Execute $PythonW -Argument $WorkerArgs -WorkingDirectory $AppRoot
        $AtLogin = New-ScheduledTaskTrigger -AtLogOn -User $Identity.Name
        $NextMinute = (Get-Date).Date.AddHours((Get-Date).Hour).AddMinutes((Get-Date).Minute + 1)
        $EveryMinute = New-ScheduledTaskTrigger -Once -At $NextMinute -RepetitionInterval (New-TimeSpan -Minutes 1)
        $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 8)
        $Principal = New-ScheduledTaskPrincipal -UserId $Identity.User.Value -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($AtLogin,$EveryMinute) -Settings $Settings -Principal $Principal -Description 'Radar local: pesquisa 19h30, envio 20h30 de Brasilia; retoma o dia ao entrar no Windows.' -Force | Out-Null
        if (Test-Path -LiteralPath $StartupLink) { Remove-Item -LiteralPath $StartupLink }
        Enable-ScheduledTask -TaskName $TaskName | Out-Null
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'Inicializacao automatica registrada no Agendador de Tarefas.'
    } catch {
        Write-Host 'Usando a pasta Inicializar do Windows para iniciar automaticamente.'
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        $Shell = New-Object -ComObject WScript.Shell
        $Shortcut = $Shell.CreateShortcut($StartupLink)
        $Shortcut.TargetPath = $PythonW
        $Shortcut.Arguments = $WorkerArgs + ' --resident'
        $Shortcut.WorkingDirectory = $AppRoot
        $Shortcut.WindowStyle = 7
        $Shortcut.Save()
        Start-Process -FilePath $PythonW -ArgumentList ($WorkerArgs + ' --resident') -WorkingDirectory $AppRoot -WindowStyle Hidden
    }
    & $VenvPython -m radar.cli test-telegram
    if ($LASTEXITCODE -ne 0) { Write-Host 'Automacao instalada; o teste Telegram falhou. Verifique internet/configuracao.' }
    Write-Host ''
    Write-Host 'PRONTO. O radar inicia ao entrar no Windows, sem abrir uma janela de CMD.'
    Write-Host 'Pesquisa: 19h30. Entrega: 20h30, sempre pelo horario de Brasilia.'
    Write-Host 'Se ligar depois das 20h30, ele tenta entregar o relatorio daquele dia.'
    Write-Host ('Pasta instalada: ' + $AppRoot)
    Write-Host ('Logs: ' + (Join-Path $AppRoot 'data\logs\radar.log'))
    exit 0
} catch {
    Write-Host ('Instalacao interrompida: ' + $_.Exception.Message)
    exit 1
}
