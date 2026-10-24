<#
.SYNOPSIS
  Runs the live .NET integration tests against a real Python service and a real PostgreSQL server.
.DESCRIPTION
  Provider-neutral: any CI system (or a developer) can call this script. It starts the Python service, waits for
  readiness, sets AMR_PYTHON_URL, and runs the live tests with AMR_REQUIRE_LIVE and AMR_REQUIRE_POSTGRES so a missing
  service or database FAILS the run instead of skipping tests, and a filter that matches no tests (or no tests in one of
  the live classes) also fails. The service process is always stopped.
  Needs AMR_TEST_POSTGRES (an admin connection string of a disposable PostgreSQL server) in the environment.
  Run from anywhere; paths are resolved from this script's location. Works in Windows PowerShell 5.1 and PowerShell 7
  on Windows and Linux; pass -Python when the interpreter is not the repository .venv.
#>
[CmdletBinding()]
param(
    [int]$Port = 8011,
    [int]$ReadinessTimeoutSeconds = 120,
    [string]$Python = $null
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$backend = Join-Path $repoRoot 'backend'
if (-not $Python) {
    $Python = Join-Path $repoRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path $Python)) { $Python = 'python' }
}
if (-not $env:AMR_TEST_POSTGRES) {
    throw 'AMR_TEST_POSTGRES is not set; the live end-to-end tests need a disposable PostgreSQL server.'
}

$url = "http://127.0.0.1:$Port"
$log = Join-Path ([IO.Path]::GetTempPath()) "amr-python-service-$Port.log"
$process = $null
$exitCode = 1
try {
    $startInfo = @{
        FilePath               = $Python
        ArgumentList           = @('-B', '-m', 'uvicorn', 'service.main:app', '--host', '127.0.0.1', '--port', "$Port", '--workers', '1')
        WorkingDirectory       = $repoRoot
        PassThru               = $true
        RedirectStandardOutput = $log
        RedirectStandardError  = "$log.err"
    }
    if ($env:OS -eq 'Windows_NT') { $startInfo.WindowStyle = 'Hidden' }
    $process = Start-Process @startInfo

    $deadline = (Get-Date).AddSeconds($ReadinessTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if ($process.HasExited) { throw "The Python service exited early with code $($process.ExitCode). See $log and $log.err." }
        try {
            $health = Invoke-RestMethod -Uri "$url/internal/health" -TimeoutSec 5
            if ($health.status -eq 'ok' -and $health.model_ready -eq $true) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "The Python service was not ready within $ReadinessTimeoutSeconds seconds. See $log and $log.err." }

    $env:AMR_PYTHON_URL = $url
    $env:AMR_REQUIRE_LIVE = 'true'
    $env:AMR_REQUIRE_POSTGRES = 'true'
    Push-Location $backend
    try {
        $env:CI = 'true'
        $liveClasses = 'LivePythonServiceTests', 'LiveEndToEndTests'
        $filter = ($liveClasses | ForEach-Object { "FullyQualifiedName~$_" }) -join '|'

        # dotnet test exits 0 when a filter matches nothing, so the selection is checked explicitly.
        $listed = @(dotnet test tests/Amr.IntegrationTests --nologo --list-tests --filter $filter)
        if ($LASTEXITCODE -ne 0) { throw 'Listing the live tests failed.' }
        $names = @($listed | Where-Object { $_ -match '^\s+Amr\.IntegrationTests\.\w+\.' })
        foreach ($class in $liveClasses) {
            if (-not ($names | Where-Object { $_ -match "\.$class\." })) { throw "The live test filter matched no tests in $class." }
        }

        dotnet test tests/Amr.IntegrationTests --nologo --no-build --filter $filter | Tee-Object -Variable testOutput
        $exitCode = $LASTEXITCODE
        $total = [regex]::Match(($testOutput -join "`n"), 'Total:\s+(\d+)')
        if ($exitCode -eq 0 -and (-not $total.Success -or [int]$total.Groups[1].Value -ne $names.Count)) {
            throw "Expected $($names.Count) live tests but the run reported $($total.Groups[1].Value)."
        }
    } finally {
        Pop-Location
    }
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit()
    }
}
exit $exitCode
