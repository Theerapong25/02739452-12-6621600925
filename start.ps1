param([switch]$NoTrigger)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.env')) {
    $chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    function New-Password([int]$length) {
        $buffer = New-Object byte[] $length
        $rng.GetBytes($buffer)
        return -join ($buffer | ForEach-Object { $chars[[int]($_ % $chars.Length)] })
    }
    $dbPass = New-Password 28
    $adminPass = New-Password 24
    $secret = New-Password 36
    @"
POSTGRES_USER=notebooks
POSTGRES_PASSWORD=$dbPass
POSTGRES_DB=notebooks
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=$adminPass
AIRFLOW_SECRET_KEY=$secret
POSTGRES_PORT=55437
AIRFLOW_PORT=8090
WEB_PORT=8502
"@ | Set-Content -Path '.env' -Encoding Ascii
    Write-Host 'Created .env with random local passwords.'
}
New-Item -ItemType Directory -Path 'data' -Force | Out-Null
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed' }
if (-not $NoTrigger) {
    for ($i = 0; $i -lt 24; $i++) {
        Start-Sleep -Seconds 5
        $ErrorActionPreference = 'Continue'
        docker compose exec -T airflow-scheduler airflow dags unpause notebook_price_comparison 2>&1 | Out-Null
        $output = docker compose exec -T airflow-scheduler airflow dags trigger notebook_price_comparison 2>&1
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($code -eq 0) { Write-Host 'Triggered notebook_price_comparison'; break }
        if ($i -eq 23) { Write-Warning 'Services started, but DAG trigger is not ready. Trigger it in the Airflow UI.' }
    }
}
Write-Host 'Dashboard: http://localhost:8502'
Write-Host 'Airflow:   http://localhost:8090'
Write-Host 'Postgres:  localhost:55437 / database notebooks'
Write-Host 'Credentials are in .env (do not commit this file).'
