$ErrorActionPreference = 'Stop'
foreach ($Script in (Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1')) {
    $Tokens = $null
    $ParseErrors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($Script.FullName, [ref]$Tokens, [ref]$ParseErrors)
    if ($ParseErrors.Count -gt 0) {
        foreach ($Problem in $ParseErrors) { Write-Host ($Script.Name + ': ' + $Problem.Message) }
        throw 'Erro de sintaxe PowerShell.'
    }
}
Write-Host 'Sintaxe PowerShell validada.'
