$ErrorActionPreference = 'Stop'
try {
    $Ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
    $DefaultExe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (-not $Ollama -and -not (Test-Path -LiteralPath $DefaultExe)) {
        $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $Winget) { throw 'Instale Ollama de https://ollama.com/download/windows e execute novamente.' }
        Write-Host 'Instalando Ollama local. Nao requer creditos OpenAI.'
        & $Winget.Source install --id Ollama.Ollama --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Instalacao do Ollama falhou.' }
        $Ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
    }
    $OllamaExe = if ($Ollama) { $Ollama.Source } else { $DefaultExe }
    $Python = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
    $Model = & $Python -c 'from radar.config import Settings; print(Settings.from_env().ollama_model)'
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel ler OLLAMA_MODEL.' }
    $RamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    Write-Host ('RAM: ' + $RamGB + ' GB. Modelo configurado: ' + $Model)
    if ($RamGB -lt 16) { Write-Host 'RAM limitada para pesquisa com 32k de contexto. Sem capacidade suficiente, o radar entregara somente dados factuais.' }
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
    catch { Start-Process -FilePath $OllamaExe -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep -Seconds 5 }
    $Installed = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10
    if (-not ($Installed.models | Where-Object { $_.name -eq $Model })) {
        Write-Host 'Baixando o modelo configurado (varios GB; pode demorar)...'
        & $OllamaExe pull $Model
        if ($LASTEXITCODE -ne 0) { throw 'Download do modelo incompleto; execute ollama pull seguido do modelo configurado.' }
    }
    & $Python -m radar.cli doctor
} catch {
    Write-Host ('IA local indisponivel: ' + $_.Exception.Message)
    Write-Host 'A automacao continuara em modo factual, sem inventar teses. Ajuste Ollama e execute INSTALAR_WINDOWS.cmd novamente.'
}
