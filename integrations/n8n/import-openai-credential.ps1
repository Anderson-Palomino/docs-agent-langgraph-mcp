# Crea en n8n la credencial "OpenAI n8n-ejercicio" con la API key que esté en el portapapeles.
# La key nunca toca el disco del host: va por stdin al contenedor, n8n la cifra al importar
# y el archivo temporal del contenedor se borra. Al final se vacía el portapapeles.
#
# Uso (desde cualquier carpeta):  powershell -ExecutionPolicy Bypass -File integrations\n8n\import-openai-credential.ps1

$ErrorActionPreference = 'Stop'
# Espera hasta 3 minutos a que copies la key: así puedes lanzar el script primero
# (copiando este comando) y después copiar la key en OpenAI.
$patron = '^sk-[A-Za-z0-9_\-]{20,}$'
Write-Host "Esperando la API key en el portapapeles (copiala en OpenAI ahora)..." -ForegroundColor Cyan
$key = $null
for ($i = 0; $i -lt 180; $i++) {
    $c = "$(Get-Clipboard -Raw)".Trim()
    if ($c -match $patron) { $key = $c; break }
    Start-Sleep -Seconds 1
}
if (-not $key) {
    Write-Host "No llego ninguna key (debe empezar con sk-) en 3 minutos. Vuelve a correr el script." -ForegroundColor Red
    exit 1
}

$cred = ConvertTo-Json -Depth 5 -Compress -InputObject @(@{
    id   = 'openAiN8nEjerc1'
    name = 'OpenAI n8n-ejercicio'
    type = 'openAiApi'
    data = @{ apiKey = $key; url = 'https://api.openai.com/v1' }
})

# Sin BOM al pasar texto por tubería a docker (PowerShell 5.1 lo agrega por defecto)
$utf8SinBom = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = $utf8SinBom
[Console]::InputEncoding = $utf8SinBom
Push-Location $PSScriptRoot
try {
    $cred | docker compose exec -T n8n sh -c 'umask 077; cat > /tmp/cred.json && n8n import:credentials --input=/tmp/cred.json; s=$?; rm -f /tmp/cred.json; exit $s'
    if ($LASTEXITCODE -ne 0) { throw "n8n import:credentials falló (código $LASTEXITCODE)" }
    Write-Host "Credencial 'OpenAI n8n-ejercicio' creada en n8n." -ForegroundColor Green
} finally {
    Pop-Location
    Set-Clipboard -Value ' '
    $key = $null; $cred = $null
    Write-Host "Portapapeles vaciado."
}
