# Optional new-PC installer. Preview by default; use -Apply to install.
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$installerName = 'weasel-0.17.4.0-installer.exe'
$archiveName = 'rime-33e7814-Windows-msvc-x64.7z'
$installerHash = 'CF509534A8F5F8AF9C98ED7CBB8F135439F145A8CBE7E50EDE42BB5B5AB45C29'
$archiveHash = '7478C7CAA4FF6B37DE86DABA1F7CE4A994A4F5BA24872A820FB2B3A9B01FED15'
$engineHash = '86B4C7357D4C6D293CE5589B234D8859CA2AC30923A03BEDFA3926EEAF97FB0B'
if (-not $Apply) {
    Write-Output 'Preview: install official Weasel 0.17.4 and librime 1.17.0 with Lua; verify SHA-256; back up any replaced engine.'
    Write-Output 'Use -Apply in an administrator PowerShell terminal for the same desktop user. This script does not reboot or remove input sources.'
    return
}
if (-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') {
    throw 'This pinned installer supports x64 Windows. Use the official platform-specific installer on other architectures.'
}
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run -Apply in an administrator PowerShell terminal.'
}
$registryPath = 'HKLM:\SOFTWARE\WOW6432Node\Rime\Weasel'
$existing = Get-ItemProperty -LiteralPath $registryPath -ErrorAction SilentlyContinue
$expectedRoot = Join-Path $env:ProgramFiles 'Rime\weasel-0.17.4'
if ($existing -and $existing.WeaselRoot.TrimEnd('\') -ne $expectedRoot.TrimEnd('\')) {
    throw 'A different Weasel installation exists. Update it manually or keep it and use setup.py with a supported engine.'
}
$cache = Join-Path $env:LOCALAPPDATA 'rime-flypy\downloads'
New-Item -ItemType Directory -Force -Path $cache | Out-Null
function Get-VerifiedDownload([string]$Url, [string]$Path, [string]$Hash) {
    if (-not (Test-Path -LiteralPath $Path)) {
        $partial = $Path + '.download'
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $partial
        if ((Get-FileHash -LiteralPath $partial).Hash -ne $Hash) { throw "Download checksum mismatch: $Url" }
        Move-Item -LiteralPath $partial -Destination $Path
    }
    if ((Get-FileHash -LiteralPath $Path).Hash -ne $Hash) { throw "Cached checksum mismatch: $Path" }
}
$installer = Join-Path $cache $installerName
$archive = Join-Path $cache $archiveName
if (-not $existing) {
    Get-VerifiedDownload "https://github.com/rime/weasel/releases/download/0.17.4/$installerName" $installer $installerHash
    $process = Start-Process -FilePath $installer -ArgumentList '/S' -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -notin @(0, 3010)) { throw "Weasel installer failed: $($process.ExitCode)" }
}
$installed = (Get-ItemProperty -LiteralPath $registryPath).WeaselRoot.TrimEnd('\')
if ($installed -ne $expectedRoot.TrimEnd('\')) { throw 'Unexpected installation directory after setup.' }
$dll = Join-Path $installed 'rime.dll'
if ((Get-FileHash -LiteralPath $dll).Hash -eq $engineHash) {
    Write-Output 'The verified Weasel/librime combination is already installed. Continue with python setup.py --apply.'
    return
}
Get-VerifiedDownload "https://github.com/rime/librime/releases/download/1.17.0/$archiveName" $archive $archiveHash
$unpacked = Join-Path $cache ('engine-' + [guid]::NewGuid().ToString('N'))
& (Join-Path $installed '7z.exe') x $archive ('-o' + $unpacked) -y
if ($LASTEXITCODE -ne 0) { throw 'Engine extraction failed.' }
$newDll = Join-Path $unpacked 'dist\lib\rime.dll'
if ((Get-FileHash -LiteralPath $newDll).Hash -ne $engineHash) { throw 'Extracted engine checksum mismatch.' }
$server = Join-Path $installed 'WeaselServer.exe'
Start-Process -FilePath $server -ArgumentList '/quit' -WindowStyle Hidden -Wait
foreach ($process in @(Get-Process -Name WeaselServer -ErrorAction SilentlyContinue | Where-Object Path -eq $server)) {
    if (-not $process.WaitForExit(5000)) { throw 'WeaselServer is still running; close it and retry.' }
}
$backup = Join-Path $env:LOCALAPPDATA ('rime-flypy\backups\engine-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -LiteralPath $dll -Destination (Join-Path $backup 'rime.dll')
try {
    Copy-Item -LiteralPath $newDll -Destination $dll -Force
    if ((Get-FileHash -LiteralPath $dll).Hash -ne $engineHash) { throw 'Installed engine checksum mismatch.' }
} catch {
    Copy-Item -LiteralPath (Join-Path $backup 'rime.dll') -Destination $dll -Force
    throw
} finally {
    Start-Process -FilePath $server -WindowStyle Hidden
}
Write-Output "Weasel 0.17.4 / librime 1.17.0 installed. Previous engine backup: $backup"
Write-Output 'Continue with python setup.py --apply, then restart Windows.'
