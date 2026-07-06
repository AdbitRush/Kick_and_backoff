# Installs "Kickbacks Guard" as a Windows Scheduled Task  runs every 30 minutes,
# starts at logon, survives reboots. Run once (as your own user, no admin needed):
#   powershell -ExecutionPolicy Bypass -File guard\install_guard_task.ps1

$repo   = Split-Path -Parent $PSScriptRoot
$python = "python"
$script = Join-Path $PSScriptRoot "kickbacks_guard.py"

$action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`" --once" -WorkingDirectory $repo
$trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
            -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
$trigger2 = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -MultipleInstances IgnoreNew

Unregister-ScheduledTask -TaskName "KickbacksGuard" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "KickbacksGuard" -Action $action `
    -Trigger $trigger1, $trigger2 -Settings $settings `
    -Description "Kickbacks session watchdog - alerts and auto relogin on silent logout"

Write-Host "OK: KickbacksGuard installed - every 30 min + at logon."
Write-Host "   Test now:   python guard\kickbacks_guard.py --once"
Write-Host "   Status:     python guard\kickbacks_guard.py --status"
