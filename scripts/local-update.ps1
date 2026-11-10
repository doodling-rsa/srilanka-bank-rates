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

# Run a native command and return its output; fail only on a non-zero exit code.
# Windows PowerShell 5.1 turns any stderr line into a terminating error under "Stop",
# so stderr (e.g. a traceback for one bank the scraper skipped) is captured as text instead.
function Run {
    param([string]$exe, [Parameter(ValueFromRemainingArguments)]$rest)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { $out = (& $exe @rest 2>&1 | ForEach-Object { "$_" }) -join "`n" }
    finally { $ErrorActionPreference = $prev }
    if ($LASTEXITCODE -ne 0) { throw "$exe $($rest -join ' ') failed ($LASTEXITCODE): $out" }
    return $out
}

# Network commands get a few tries: brief connection resets to GitHub do happen.
function RunWithRetry {
    param([string]$exe, [Parameter(ValueFromRemainingArguments)]$rest)
    for ($i = 1; ; $i++) {
        try { return Run $exe @rest }
        catch {
            if ($i -ge 4) { throw }
            Log "retry $i after error: $($_.Exception.Message.Split("`n")[0])"
            Start-Sleep -Seconds (20 * $i)
        }
    }
}

try {
    Log "start"
    # Only publish from main; skip quietly if the folder is checked out on another branch.
    $branch = (Run git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -ne "main") { Log "skipped: on branch '$branch', not main"; exit 0 }
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        # This script owns data/rates.json: drop any leftover edits so the fast-forward can't be blocked.
        Run git restore -- data/rates.json | Out-Null
        RunWithRetry git fetch -q origin main | Out-Null
        Run git merge -q --ff-only origin/main | Out-Null

        $out = Run python scraper/run.py --backfill-days 14
        Log ((($out.Trim() -split "`r?`n") | Where-Object { $_ -match "^(cbsl|\w+ +(TT|FAILED))|wrote" }) -join " | ")

        & git diff --quiet -- data/rates.json
        if ($LASTEXITCODE -eq 0) { Log "no changes"; break }

        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
        Run git commit -q -m "Rates update (local) $stamp" -- data/rates.json | Out-Null
        try { RunWithRetry git push -q origin main | Out-Null; Log "pushed"; break }
        catch {
            # Usually GitHub's scheduled run pushed first: drop our commit and redo on top of it.
            Log "push failed, redoing on latest main ($attempt): $($_.Exception.Message.Split("`n")[0])"
            Run git reset -q --soft HEAD~1 | Out-Null
            Run git restore --staged --worktree -- data/rates.json | Out-Null
            if ($attempt -eq 3) { throw "push failed 3 times" }
            Start-Sleep -Seconds 10
        }
    }
    Log "done"
}
catch {
    Log ("ERROR: " + ($_.Exception.Message -replace "`r?`n", " | "))
    exit 1
}
