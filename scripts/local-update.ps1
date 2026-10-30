# Scrape all sources from this PC (Sri Lankan IP) and push data/rates.json.
# CBSL, BOC, Commercial and NTB block GitHub's servers, so they're only updated by this script.
# The push triggers the GitHub workflow, which redeploys the site.
#
# Run manually:  powershell -ExecutionPolicy Bypass -File scripts\local-update.ps1
# Scheduled by:  scripts\install-task.ps1

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "local-update.log"
function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Out-File $log -Append -Encoding utf8 }

# Native commands: fail on non-zero exit codes.
function Run {
    param([string]$exe, [Parameter(ValueFromRemainingArguments)]$rest)
    $out = & $exe @rest 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "$exe $($rest -join ' ') failed ($LASTEXITCODE): $out" }
    return $out
}

try {
    Log "start"
    # Only publish from main; skip quietly if the folder is checked out on another branch.
    $branch = (Run git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -ne "main") { Log "skipped: on branch '$branch', not main"; exit 0 }
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Run git fetch -q origin main | Out-Null
        Run git merge -q --ff-only origin/main | Out-Null

        $out = Run python scraper/run.py --backfill-days 14
        Log ((($out.Trim() -split "`r?`n") | Where-Object { $_ -match "^(cbsl|\w+ +(TT|FAILED))|wrote" }) -join " | ")

        & git diff --quiet -- data/rates.json
        if ($LASTEXITCODE -eq 0) { Log "no changes"; break }

        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
        Run git commit -q -m "Rates update (local) $stamp" -- data/rates.json | Out-Null
        & git push -q origin main 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Log "pushed"; break }

        # GitHub's scheduled run pushed first: drop our commit, restore the file, and redo on top of it.
        Log "push rejected, retrying ($attempt)"
        Run git reset -q --soft HEAD~1 | Out-Null
        Run git restore --staged --worktree -- data/rates.json | Out-Null
        Start-Sleep -Seconds 10
        if ($attempt -eq 3) { throw "push failed 3 times" }
    }
    Log "done"
}
catch {
    Log "ERROR: $_"
    exit 1
}
