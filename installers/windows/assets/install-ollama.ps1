$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$installDir = Join-Path $env:LOCALAPPDATA 'Programs\Ollama'
$env:OLLAMA_INSTALL_DIR = $installDir

try {
	if (-not (Test-Path $installDir)) {
		New-Item -ItemType Directory -Path $installDir -Force | Out-Null
	}
} catch {
	# Keep going: fallback installer can still choose a valid destination.
}

$installed = $false

try {
	[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
	Invoke-RestMethod -Uri 'https://ollama.com/install.ps1' -UseBasicParsing | Invoke-Expression
	$installed = $true
} catch {
	Write-Host "Ollama online installer failed: $($_.Exception.Message)"
}

if (-not $installed) {
	$offlineInstaller = Join-Path $PSScriptRoot 'OllamaSetup.exe'
	if (Test-Path $offlineInstaller) {
		try {
			# Attempt silent install first; installer-specific flags may vary by version.
			Start-Process -FilePath $offlineInstaller -ArgumentList '/S' -Wait
			$installed = $true
		} catch {
			Write-Host "Ollama offline installer failed: $($_.Exception.Message)"
		}
	}
}

# Never fail the parent setup wizard because of Ollama installation issues.
exit 0
