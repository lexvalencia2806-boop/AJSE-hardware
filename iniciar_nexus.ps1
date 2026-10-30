$ErrorActionPreference = "Stop"

$pythonPath = @(
    (Join-Path $PSScriptRoot ".venv-1\Scripts\python.exe"),
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $pythonPath) {
    throw "No encontré Python del entorno virtual (.venv-1 o .venv)."
}

$secureKey = Read-Host "Ingresa tu clave de Gemini API (no se guardará en archivos)" -AsSecureString
if ($secureKey.Length -eq 0) {
    throw "La clave de Gemini API no puede estar vacía."
}

$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    & $pythonPath (Join-Path $PSScriptRoot "app.py")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    $secureKey.Dispose()
}
