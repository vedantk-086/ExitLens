param(
    [Parameter(Mandatory = $false)]
    [string]$RepoPath = ""
)

$ErrorActionPreference = "Stop"
$BundleRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    throw "First fork https://github.com/rishrek/LinkWatch on GitHub and clone YOUR fork locally. Rerun with -RepoPath <path-to-your-local-fork>. This script intentionally will not create an unrelated clone that could be mistaken for the required fork."
}
$RepoPath = [System.IO.Path]::GetFullPath($RepoPath)

Write-Host "ExitLens scaffold bootstrap" -ForegroundColor Cyan
Write-Host "Target folder: $RepoPath"

if (-not (Test-Path $RepoPath)) {
    throw "The provided RepoPath does not exist. Clone your GitHub fork first, then pass its local path using -RepoPath."
}

$GitDir = Join-Path $RepoPath ".git"
$PyProject = Join-Path $RepoPath "pyproject.toml"
$LinkWatchPackage = Join-Path $RepoPath "linkwatch"
if (-not (Test-Path $GitDir) -or -not (Test-Path $PyProject) -or -not (Test-Path $LinkWatchPackage)) {
    throw "The target does not look like a LinkWatch Git checkout (expected .git, pyproject.toml and linkwatch/). No overlay was applied."
}
$OriginUrl = (& git -C $RepoPath remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($OriginUrl)) {
    throw "No Git origin remote was found. Set origin to your public GitHub fork before applying the scaffold."
}
if ($OriginUrl.Trim() -match "github\.com[:/]rishrek/LinkWatch(?:\.git)?/?$") {
    throw "The origin remote points to the official upstream repository, not your fork. Fork LinkWatch on GitHub, clone your fork, and rerun this script."
}

$DocsDest = Join-Path $RepoPath "docs"
$UpstreamDocs = Join-Path $DocsDest "upstream"
New-Item -ItemType Directory -Path $UpstreamDocs -Force | Out-Null
$RootReadme = Join-Path $RepoPath "README.md"
$BackupReadme = Join-Path $UpstreamDocs "README-LinkWatch.md"
if ((Test-Path $RootReadme) -and -not (Test-Path $BackupReadme)) {
    Copy-Item $RootReadme $BackupReadme
    Write-Host "Preserved upstream README at docs/upstream/README-LinkWatch.md"
}

# Copy tree contents by relative path, merging folders instead of producing nested docs/docs directories.
function Copy-TreeContents([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        $DestinationItem = Join-Path $Destination $_.Name
        if ($_.PSIsContainer) {
            Copy-TreeContents $_.FullName $DestinationItem
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $DestinationItem -Force
        }
    }
}

# Copy the ExitLens root README and additive docs.
Copy-Item (Join-Path $BundleRoot "README.md") $RootReadme -Force
Copy-TreeContents (Join-Path $BundleRoot "docs") $DocsDest
Copy-TreeContents (Join-Path $BundleRoot "contracts") (Join-Path $RepoPath "contracts")
Copy-TreeContents (Join-Path $BundleRoot "exitlens_app") (Join-Path $RepoPath "exitlens_app")
Copy-TreeContents (Join-Path $BundleRoot "reports") (Join-Path $RepoPath "reports")
Copy-TreeContents (Join-Path $BundleRoot "scripts") (Join-Path $RepoPath "scripts")

# Merge ignore rules; do not replace the upstream .gitignore.
$IgnoreFile = Join-Path $RepoPath ".gitignore"
if (-not (Test-Path $IgnoreFile)) { New-Item -ItemType File -Path $IgnoreFile | Out-Null }
$Marker = "# --- ExitLens generated/local files (managed by scaffold) ---"
$CurrentIgnore = Get-Content $IgnoreFile -Raw
if (-not $CurrentIgnore.Contains($Marker)) {
    $IgnoreBlock = @'

# --- ExitLens generated/local files (managed by scaffold) ---
# local configuration and secrets
**/.env
**/.env.*.local
!**/.env.example
# Python local environments and caches
**/.venv/
**/venv/
**/__pycache__/
**/.pytest_cache/
**/.ruff_cache/
*.py[cod]
# Frontend dependencies/build output
**/node_modules/
**/dist/
# ExitLens generated analyses and artifacts (keep only the directory marker)
reports/exitlens/**
!reports/exitlens/.gitkeep
'@
    Add-Content -Path $IgnoreFile -Value $IgnoreBlock
}

# Upstream license/metadata must remain in place; never overwrite those files.
if (-not (Test-Path (Join-Path $RepoPath "LICENSE"))) {
    Write-Warning "No root LICENSE was found. Review upstream licensing requirements before submission; the scaffold did not invent or add a license."
}

Write-Host "Scaffold overlay complete." -ForegroundColor Green
Write-Host "No ExitLens application logic was generated. Review the changes, then commit this scaffold before implementation."
Write-Host "Next: read README.md, docs/IMPLEMENTATION_CHECKLIST.md, docs/API_CONTRACT.md, and both layer READMEs."
Write-Host "Verify upstream source and license remain present with: git status --short"
