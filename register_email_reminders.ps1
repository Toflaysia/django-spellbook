param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$taskName = 'SpellbookEmailReminders'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host 'Reminder task removed.'
    exit 0
}
$python = Join-Path $root '.venv\Scripts\python.exe'
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$runner = Join-Path $root 'spells\management\run_reminders.py'
if (!(Test-Path $python) -or !(Test-Path $runner)) { throw 'Copy this script next to manage.py and install iteration 6 first.' }
# Check configuration without sending any messages.
& $python (Join-Path $root 'manage.py') shell -c "from django.conf import settings; import sys; sys.exit(0 if settings.SPELLBOOK_EMAIL_DELIVERY_ENABLED else 1)"
if ($LASTEXITCODE -ne 0) { throw 'Configure email_settings.json before registering the reminder task.' }
if (!(Test-Path $pythonw)) { $pythonw = $python }
$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + $runner + '"') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host 'Reminder task registered: every 15 minutes while this Windows user is logged in.'
Write-Host 'Log: logs\email_reminders.log'
