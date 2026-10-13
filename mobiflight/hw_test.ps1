# 实物测试: 逐路点亮 LED 并记录按键事件。运行前需关闭 MobiFlight Connector。
param(
  [string]$Port = "COM5",
  [int]$StepMs = 1500,
  [int]$ListenSec = 90,
  [string]$Only = ""
)

$leds = [ordered]@{
  "3" = "J1 上 GEAR1_UNLK"; "2" = "J1 下 GEAR1_DOWN"
  "5" = "J2 上 GEAR2_UNLK"; "4" = "J2 下 GEAR2_DOWN"
  "7" = "J3 上 GEAR3_UNLK"; "6" = "J3 下 GEAR3_DOWN"
  "9" = "J4 上 ABRK_LO_DECEL"; "8" = "J4 下 ABRK_LO_ON"
  "11" = "J5 上 ABRK_MED_DECEL"; "10" = "J5 下 ABRK_MED_ON"
  "13" = "J6 上 ABRK_MAX_DECEL"; "12" = "J6 下 ABRK_MAX_ON"
  "15" = "J7 上 BRKFAN_HOT"; "14" = "J7 下 BRKFAN_ON"
  "17" = "J8 上 GEAR_ARROW"; "16" = "J8 下 TERR_ON"
}
if ($Only) {
  $keep = $Only.Split(",") | % { $_.Trim() }
  foreach ($k in @($leds.Keys)) { if ($keep -notcontains $k) { $leds.Remove($k) } }
}
$buttons = @("ASKID_SW", "GEAR_LEVER_SW", "ABRK_LO_BTN", "ABRK_MED_BTN", "ABRK_MAX_BTN", "BRKFAN_BTN", "TERR_BTN")
$seen = @{}

$sp = New-Object System.IO.Ports.SerialPort $Port, 115200
$sp.DtrEnable = $true
$sp.ReadTimeout = 50
$sp.Open()
Start-Sleep -Milliseconds 2500
$sp.DiscardInBuffer()
$buf = ""

function Log($msg) { Write-Output ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg) }

function Pump {
  $script:buf += $sp.ReadExisting()
  while ($script:buf.Contains(";")) {
    $i = $script:buf.IndexOf(";")
    $msg = $script:buf.Substring(0, $i).Trim()
    $script:buf = $script:buf.Substring($i + 1)
    $f = $msg.Split(",")
    if ($f[0] -eq "7") {
      $state = if ($f[2] -eq "0") { "按下/闭合" } else { "松开/断开" }
      if (-not $script:seen.ContainsKey($f[1])) { $script:seen[$f[1]] = @{} }
      $script:seen[$f[1]][$f[2]] = $true
      Log "按键 $($f[1]) -> $state"
    } elseif ($msg) {
      Log "固件: $msg"
    }
  }
}

function SetPin($pin, $val) { $sp.Write("2,$pin,$val;") }

try {
  foreach ($p in $leds.Keys) { SetPin $p 0 }
  Log "开关当前状态 (Retrigger):"
  $sp.Write("23;")
  Start-Sleep -Milliseconds 500
  Pump
  $seen.Clear()

  Log "=== 逐路点灯，每路 $StepMs ms ==="
  foreach ($p in $leds.Keys) {
    Log ("点亮 D{0,-2} {1}" -f $p, $leds[$p])
    SetPin $p 255
    $t = [DateTime]::Now.AddMilliseconds($StepMs)
    while ([DateTime]::Now -lt $t) { Pump; Start-Sleep -Milliseconds 30 }
    SetPin $p 0
  }
  Log "=== 全部点亮 3 秒 ==="
  foreach ($p in $leds.Keys) { SetPin $p 255 }
  $t = [DateTime]::Now.AddSeconds(3); while ([DateTime]::Now -lt $t) { Pump; Start-Sleep -Milliseconds 30 }
  foreach ($p in $leds.Keys) { SetPin $p 0 }

  Log "=== 按键监听 $ListenSec 秒: 请把每个按钮按一下、每个开关拨一个来回 ==="
  $t = [DateTime]::Now.AddSeconds($ListenSec)
  while ([DateTime]::Now -lt $t) {
    Pump
    $done = @($buttons | ? { $seen.ContainsKey($_) -and $seen[$_].ContainsKey("0") -and $seen[$_].ContainsKey("1") })
    if ($done.Count -eq $buttons.Count) { Log "7 个输入都已检测到按下和松开"; break }
    Start-Sleep -Milliseconds 30
  }
} finally {
  foreach ($p in $leds.Keys) { SetPin $p 0 }
  $sp.Close()
}

Log "=== 按键结果 ==="
foreach ($b in $buttons) {
  $press = $seen.ContainsKey($b) -and $seen[$b].ContainsKey("0")
  $rel = $seen.ContainsKey($b) -and $seen[$b].ContainsKey("1")
  Log ("{0,-14} 按下:{1}  松开:{2}" -f $b, $(if ($press) { "OK" } else { "--" }), $(if ($rel) { "OK" } else { "--" }))
}
