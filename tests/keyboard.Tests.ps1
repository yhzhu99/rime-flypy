$ErrorActionPreference = 'Stop'
# Plan reads the registry but never writes it. Import the pure map functions.
. (Join-Path $PSScriptRoot '..\platforms\windows\keyboard.ps1') -Action Plan | Out-Null
function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
$fresh = New-PersonalKeyboardMap $null
$entries = @(Get-ScanEntries $fresh)
Assert-True ($entries.Count -eq 5) 'Fresh map must have exactly five mappings.'
Assert-True ((ConvertTo-MapHex (New-PersonalKeyboardMap $fresh)) -eq (ConvertTo-MapHex $fresh)) 'Apply must be idempotent.'
foreach ($pair in @(@(0x1, 0x3a), @(0x3a, 0x1), @(0x1d, 0x38), @(0x38, 0x1d), @(0xe038, 0x64))) {
    $found = @($entries | Where-Object Source -eq $pair[0])
    Assert-True ($found.Count -eq 1 -and $found[0].Destination -eq $pair[1]) 'Wrong physical-key mapping.'
}
# Existing unrelated A -> B mapping survives; a conflicting right Alt map is replaced.
$existing = ConvertFrom-MapHex '00000000000000000300000030001e001de038e000000000'
$merged = @(Get-ScanEntries (New-PersonalKeyboardMap $existing))
Assert-True ($merged.Count -eq 6) 'Merge must preserve unrelated mappings without duplicating sources.'
Assert-True (($merged | Where-Object Source -eq 0x1e).Destination -eq 0x30) 'Unrelated map was lost.'
Assert-True (($merged | Where-Object Source -eq 0xe038).Destination -eq 0x64) 'Right Alt was not updated.'
$rejected = $false
try { Get-ScanEntries ([byte[]]@(0, 0, 0)) | Out-Null } catch { $rejected = $true }
Assert-True $rejected 'Malformed registry data must be rejected.'
$duplicate = ConvertFrom-MapHex '00000000000000000300000030001e0031001e0000000000'
$rejected = $false
try { Get-ScanEntries $duplicate | Out-Null } catch { $rejected = $true }
Assert-True $rejected 'Duplicate source scancodes must be rejected.'
Write-Output 'Keyboard mapping behavior tests passed; registry was not modified.'
