# 用 MobiFlight Connector 本体加载、保存、重新加载项目与 mfmc（需 32 位 PowerShell）:
# C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File test_mobiflight_load.ps1
param([string]$MfDir = "$env:LOCALAPPDATA\MobiFlight\MobiFlight Connector")

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$fail = 0
function Check($cond, $msg) { if (-not $cond) { Write-Output "  FAIL: $msg"; $script:fail++ } }

Set-Location $MfDir
[void][Reflection.Assembly]::LoadFrom("$MfDir\MFConnector.exe")
Write-Output ("MobiFlight " + (Get-Item "$MfDir\MFConnector.exe").VersionInfo.FileVersion)

$p = New-Object MobiFlight.Base.Project
$p.FilePath = Join-Path $here "A320_AGP_Fenix.mfproj"
$p.OpenFile($true)
$p.DetermineProjectInfos()
$items = $p.ConfigFiles[0].ConfigItems
Check ($p.Sim -eq "msfs") "Sim=$($p.Sim)"
Check ($items.Count -eq 23) "配置项数量 $($items.Count)"
foreach ($i in $items) {
  Check ($i.Device -ne $null) "$($i.Name): Device 为空"
  Check ($i.Controller.Name -eq "A320 AGP") "$($i.Name): 控制器 $($i.Controller)"
  if ($i -is [MobiFlight.OutputConfigItem]) {
    Check ($i.Source -is [MobiFlight.Base.SimConnectSource]) "$($i.Name): Source 类型"
    Check ($i.Source.SimConnectValue.VarType -eq [MobiFlight.OutputConfig.SimConnectVarType]::CODE) "$($i.Name): VarType"
    Check ($i.DeviceType -eq "Output") "$($i.Name): DeviceType"
  } else {
    Check ($i.button.onPress -is [MobiFlight.InputConfig.MSFS2020CustomInputAction]) "$($i.Name): onPress 类型"
    Check ($i.button.onRelease -is [MobiFlight.InputConfig.MSFS2020CustomInputAction]) "$($i.Name): onRelease 类型"
  }
}

$tmp = Join-Path $env:TEMP "a320_agp_roundtrip.mfproj"
$p.FilePath = $tmp
$p.SaveFile()
$q = New-Object MobiFlight.Base.Project
$q.FilePath = $tmp
$q.OpenFile($true)
$q2 = $q.ConfigFiles[0].ConfigItems
for ($k = 0; $k -lt $items.Count; $k++) {
  Check ($items[$k].Equals($q2[$k])) "往返后不一致: $($items[$k].Name)"
}
Remove-Item $tmp

$ser = New-Object System.Xml.Serialization.XmlSerializer([MobiFlight.Config.Config])
$fs = [IO.File]::OpenRead((Join-Path $here "A320_AGP_Mega.mfmc"))
$cfg = $ser.Deserialize($fs); $fs.Close()
Check ($cfg.ModuleName -eq "A320 AGP") "mfmc ModuleName"
Check ($cfg.Items.Count -eq 23) "mfmc 设备数 $($cfg.Items.Count)"
$cfgStr = ($cfg.ToInternal(90) -join "")
Write-Output "固件配置串 $($cfgStr.Length) 字节: $cfgStr"

$names = @($cfg.Items | % { $_.Name })
foreach ($i in $items) {
  $dev = if ($i -is [MobiFlight.OutputConfigItem]) { $i.Device.Pin } else { $i.DeviceName }
  Check ($names -contains $dev) "项目引用的设备 $dev 不在 mfmc 中"
}

Write-Output ("结果: " + $(if ($fail) { "失败 $fail 项" } else { "全部通过" }))
exit $fail
