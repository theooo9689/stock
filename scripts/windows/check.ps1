$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
foreach ($Name in @('install.ps1','uninstall.ps1','setup-ollama.ps1','setup-codex.ps1','forward-pdf.ps1')) {
    $Tokens = $null
    $ParseErrors = $null
    $Ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $Name), [ref]$Tokens, [ref]$ParseErrors)
    if ($ParseErrors.Count -gt 0) { throw ('Script PowerShell invalido: ' + $Name) }
    if ($Name -eq 'install.ps1') {
        $Function = $Ast.Find({ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq 'Find-RadarPython' }, $true)
        if (-not $Function) { throw 'Funcao de deteccao do Python ausente.' }
        Invoke-Expression $Function.Extent.Text
        $Python = Find-RadarPython
        if (-not $Python) { throw 'Python 3.12+ nao detectado no runner Windows.' }
        & $Python -c "import sys; assert sys.version_info >= (3,12)"
        if ($LASTEXITCODE -ne 0) { throw 'Python detectado nao atende a versao minima.' }
        & python.exe -c "from zoneinfo import ZoneInfo; import radar.pipeline; print(ZoneInfo('America/Sao_Paulo'))"
        if ($LASTEXITCODE -ne 0) { throw 'Falha no import nativo Windows/fuso.' }
    }
}
Write-Host 'Scripts PowerShell e import Windows validados; nenhuma tarefa foi instalada neste teste.'
