# Run Plan without elevation. Apply and Undo require an administrator shell.
[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Apply', 'Undo')][string]$Action = 'Plan',
    [string]$BackupPath
)
$ErrorActionPreference = 'Stop'

function ConvertTo-MapHex([AllowNull()][byte[]]$Bytes) {
    if ($null -eq $Bytes) { return $null }
    return ([BitConverter]::ToString($Bytes)).Replace('-', '').ToLowerInvariant()
}

function ConvertFrom-MapHex([string]$Hex) {
    if ($Hex -notmatch '^(?:[0-9a-fA-F]{2})+$') { throw 'Invalid mapping backup hex.' }
    [byte[]]$bytes = for ($i = 0; $i -lt $Hex.Length; $i += 2) {
        [Convert]::ToByte($Hex.Substring($i, 2), 16)
    }
    return ,$bytes
}

function Get-ScanEntries([AllowNull()][byte[]]$Bytes) {
    if ($null -eq $Bytes) { return }
    if ($Bytes.Length -lt 16 -or (ConvertTo-MapHex $Bytes[0..7]) -ne '0000000000000000') {
        throw 'Invalid Scancode Map header.'
    }
    $count = [BitConverter]::ToUInt32($Bytes, 8)
    if ($count -lt 1 -or $Bytes.Length -ne (12 + 4 * [long]$count) -or
        [BitConverter]::ToUInt32($Bytes, $Bytes.Length - 4) -ne 0) {
        throw 'Invalid Scancode Map length or terminator.'
    }
    $seen = @{}
    for ($i = 0; $i -lt $count - 1; $i++) {
        $destination = [BitConverter]::ToUInt16($Bytes, 12 + 4 * $i)
        $source = [BitConverter]::ToUInt16($Bytes, 14 + 4 * $i)
        if ($source -eq 0 -or $seen.ContainsKey([int]$source)) { throw 'Invalid or duplicate source scancode.' }
        $seen[[int]$source] = $true
        [pscustomobject]@{ Source = [int]$source; Destination = [int]$destination }
    }
}

function New-PersonalKeyboardMap([AllowNull()][byte[]]$Before) {
    $entries = [ordered]@{}
    foreach ($entry in @(Get-ScanEntries $Before)) {
        $entries[$entry.Source.ToString('X4')] = [int]$entry.Destination
    }
    # Physical keys: Escape/Caps Lock, left Ctrl/Alt, right Alt -> F13.
    $desired = @(
        @(0x0001, 0x003a), @(0x003a, 0x0001),
        @(0x001d, 0x0038), @(0x0038, 0x001d), @(0xe038, 0x0064)
    )
    foreach ($pair in $desired) { $entries[$pair[0].ToString('X4')] = [int]$pair[1] }
    $bytes = [Collections.Generic.List[byte]]::new()
    $bytes.AddRange([byte[]]::new(8))
    $bytes.AddRange([BitConverter]::GetBytes([uint32]($entries.Count + 1)))
    foreach ($entry in $entries.GetEnumerator()) {
        $bytes.AddRange([BitConverter]::GetBytes([uint16]$entry.Value))
        $bytes.AddRange([BitConverter]::GetBytes([Convert]::ToUInt16($entry.Key, 16)))
    }
    $bytes.AddRange([byte[]]::new(4))
    return ,$bytes.ToArray()
}

$registryPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Keyboard Layout'
$properties = Get-ItemProperty -LiteralPath $registryPath
$before = $properties.'Scancode Map'
$after = New-PersonalKeyboardMap $before
$beforeHex = ConvertTo-MapHex $before
$afterHex = ConvertTo-MapHex $after
if ($Action -eq 'Plan') {
    [pscustomobject]@{ changed = $beforeHex -ne $afterHex; beforeHex = $beforeHex; afterHex = $afterHex }
    return
}
if ($Action -eq 'Apply' -and $beforeHex -eq $afterHex) {
    Write-Output 'Desired mappings are already stored. No backup or registry changes made. A pending mapping still requires restart.'
    return
}
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run Apply/Undo from an administrator PowerShell window.'
}
if ($Action -eq 'Undo') {
    if (-not $BackupPath) { throw 'Undo requires -BackupPath from an earlier Apply.' }
    $backup = Get-Content -LiteralPath $BackupPath -Raw | ConvertFrom-Json
    if ($backup.version -ne 1 -or $beforeHex -ne $backup.afterHex) {
        throw 'Mapping differs from the backup result; refusing to overwrite later changes.'
    }
    if ($null -eq $backup.beforeHex) {
        Remove-ItemProperty -LiteralPath $registryPath -Name 'Scancode Map'
    } else {
        $restored = ConvertFrom-MapHex $backup.beforeHex
        @(Get-ScanEntries $restored) | Out-Null
        Set-ItemProperty -LiteralPath $registryPath -Name 'Scancode Map' -Value $restored
    }
    $actual = (Get-ItemProperty -LiteralPath $registryPath).'Scancode Map'
    if ((ConvertTo-MapHex $actual) -ne $backup.beforeHex) { throw 'Rollback readback mismatch.' }
    Write-Output 'Previous mappings restored. Restart Windows to activate them.'
    return
}
if (-not $BackupPath) {
    $backupDirectory = Join-Path $env:LOCALAPPDATA 'rime-flypy\backups'
    New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null
    $BackupPath = Join-Path $backupDirectory ('keyboard-' + [guid]::NewGuid().ToString('N') + '.json')
}
if (Test-Path -LiteralPath $BackupPath) { throw 'Backup already exists; choose a new path.' }
[ordered]@{ version = 1; beforeHex = $beforeHex; afterHex = $afterHex } |
    ConvertTo-Json | Set-Content -LiteralPath $BackupPath -Encoding UTF8
Set-ItemProperty -LiteralPath $registryPath -Name 'Scancode Map' -Value $after
$actual = (Get-ItemProperty -LiteralPath $registryPath).'Scancode Map'
if ((ConvertTo-MapHex $actual) -ne $afterHex) { throw 'Registry readback mismatch.' }
Write-Output "Mappings saved. Backup: $BackupPath"
Write-Output 'Restart Windows to activate them.'
