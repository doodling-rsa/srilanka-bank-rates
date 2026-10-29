# Register a Windows scheduled task that runs local-update.ps1 at 10:00 and 15:00 every day.
# Missed runs (PC asleep/off) run as soon as the PC is available again.
# Re-run this script to update the task; remove it with:
#   Unregister-ScheduledTask -TaskName "USD-LKR rates update" -Confirm:$false

$name = "USD-LKR rates update"
$script = Join-Path $PSScriptRoot "local-update.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$triggers = @(
    New-ScheduledTaskTrigger -Daily -At "10:00"
    New-ScheduledTaskTrigger -Daily -At "15:00"
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
# Interactive = runs as you while you're signed in, so git can use your saved GitHub credentials.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings `
    -Principal $principal -Description "Scrape USD/LKR bank + CBSL rates and push to GitHub" -Force |
    Select-Object TaskName, State
