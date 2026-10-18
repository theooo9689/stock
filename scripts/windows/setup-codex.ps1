$ErrorActionPreference = 'Stop'
try {
    $Codex = Get-Command codex.exe -ErrorAction SilentlyContinue
    if (-not $Codex) { $Codex = Get-Command codex.cmd -ErrorAction SilentlyContinue }
    $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    $DefaultNpm = Join-Path $env:ProgramFiles 'nodejs\npm.cmd'
    if (-not $Codex -and -not $Npm -and -not (Test-Path -LiteralPath $DefaultNpm)) {
        $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $Winget) { throw 'Instale Node.js LTS de https://nodejs.org e execute novamente.' }
        Write-Host 'Instalando Node.js LTS para usar o Codex CLI oficial...'
        & $Winget.Source install --id OpenJS.NodeJS.LTS --exact --source winget --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Instale Node.js LTS de https://nodejs.org e execute novamente.' }
    }
    $NodeDir = Join-Path $env:ProgramFiles 'nodejs'
    $NpmBin = Join-Path $env:APPDATA 'npm'
    $env:PATH = $NodeDir + ';' + $NpmBin + ';' + $env:PATH
    if (-not $Codex) {
        $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $Npm) { throw 'npm nao localizado. Abra um novo CMD apos instalar Node.js LTS.' }
        Write-Host 'Instalando CLI oficial @openai/codex; nenhum modelo Ollama sera baixado.'
        & $Npm.Source install --global @openai/codex
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar @openai/codex.' }
    }
    $Python = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
    & $Python -m radar.cli doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Entre uma vez na conta ChatGPT Plus usando o fluxo oficial do Codex.'
        $CodexPath = & $Python -c 'from radar.codex_research import command_path; print(command_path())'
        if ($LASTEXITCODE -ne 0) { throw 'Codex nativo nao localizado.' }
        & $CodexPath login
        if ($LASTEXITCODE -ne 0) { throw 'Login nao concluido. Execute codex login e rode este instalador novamente.' }
        & $Python -m radar.cli doctor
        if ($LASTEXITCODE -ne 0) { throw 'Login ChatGPT nao confirmado; autenticacao por API nao e aceita pelo radar.' }
    }
} catch {
    Write-Host ('Configuracao Codex pendente: ' + $_.Exception.Message)
    throw 'A tarefa automatica nao foi ativada. Conclua o login ChatGPT e execute o instalador novamente.'
}
