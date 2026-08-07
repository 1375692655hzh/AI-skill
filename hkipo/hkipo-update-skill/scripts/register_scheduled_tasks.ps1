<#
.SYNOPSIS
  Register Windows Task Scheduler entries for the HK IPO skill.

.DESCRIPTION
  Creates 8 scheduled tasks (1 daily update + 6 reminder slots + 1 weekly cleanup).
  Tasks run only on weekdays for the update/remind slots (HKEX trading days
  approximation) and on Sundays for cleanup. Holidays are NOT filtered here —
  the skill itself checks trading days via config.holidays + built-in HKEX list.

.PARAMETER SkillRoot
  Absolute path to the hkipo-update-skill directory. Defaults to the parent of
  this script's location.

.PARAMETER Python
  Python executable to call. Defaults to 'python' on PATH.

.PARAMETER Uninstall
  Switch to delete the 8 tasks instead of creating them.

.EXAMPLE
  .\register_scheduled_tasks.ps1 -SkillRoot "D:\AI-skills-git\hkipo\hkipo-update-skill"
#>

[CmdletBinding()]
param(
    [string]$SkillRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Python    = "python",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SkillRoot)) {
    throw "SkillRoot does not exist: $SkillRoot"
}

$configPath = Join-Path $SkillRoot "config.json"
if (-not (Test-Path $configPath)) {
    Write-Warning "config.json not found at $configPath — copying from config.example.json"
    Copy-Item (Join-Path $SkillRoot "config.example.json") $configPath
}

$TaskPrefix = "HKIPO_"

# (TaskName, DayOfWeek filter, StartTime, Script, Args)
$Tasks = @(
    @{ Name = "Update";       Days = "MON,TUE,WED,THU,FRI"; Time = "07:30";
       Script = "run_update.py";     Args = "" },
    @{ Name = "Remind_CashClose";   Days = "MON,TUE,WED,THU,FRI"; Time = "08:30";
       Script = "run_remind.py";     Args = "--type cash_close" },
    @{ Name = "Remind_OfferOpen";   Days = "MON,TUE,WED,THU,FRI"; Time = "09:00";
       Script = "run_remind.py";     Args = "--type offer_open" },
    @{ Name = "Remind_MarginClose"; Days = "MON,TUE,WED,THU,FRI"; Time = "13:30";
       Script = "run_remind.py";     Args = "--type margin_close" },
    @{ Name = "Remind_GreyOpen";    Days = "MON,TUE,WED,THU,FRI"; Time = "16:00";
       Script = "run_remind.py";     Args = "--type grey_open" },
    @{ Name = "Remind_Refund";      Days = "MON,TUE,WED,THU,FRI"; Time = "17:00";
       Script = "run_remind.py";     Args = "--type refund" },
    @{ Name = "Remind_GreyClose";   Days = "MON,TUE,WED,THU,FRI"; Time = "18:15";
       Script = "run_remind.py";     Args = "--type grey_close" },
    @{ Name = "Cleanup";            Days = "SUN";                 Time = "03:00";
       Script = "cleanup_listed.py"; Args = "" }
)

foreach ($t in $Tasks) {
    $taskName = "$TaskPrefix$($t.Name)"
    $scriptPath = Join-Path $SkillRoot "scripts\$($t.Script)"
    $command = "$Python `"$scriptPath`" --config `"$configPath`" $($t.Args)"

    if ($Uninstall) {
        Write-Host "Deleting task $taskName ..."
        schtasks /Delete /TN $taskName /F | Out-Null
        continue
    }

    Write-Host "Registering $taskName (days=$($t.Days) time=$($t.Time))"
    Write-Host "  cmd: $command"

    schtasks /Create /SC WEEKLY /D $t.Days /ST $t.Time /TN $taskName `
        /TR $command /F | Out-Null

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to register $taskName (exit $LASTEXITCODE). Run PowerShell as Administrator."
    }
}

if ($Uninstall) {
    Write-Host "`nAll $TaskPrefix* tasks deleted."
} else {
    Write-Host "`nDone. Verify with: schtasks /Query /TN HKIPO_* /FO LIST"
    Write-Host "Tip: set BARK_KEY / WECOM_WEBHOOK / SC_KEY env vars in the SYSTEM scope"
    Write-Host "     (System Properties -> Environment Variables) so scheduled tasks can read them."
}
