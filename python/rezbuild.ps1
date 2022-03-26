$ProjectName = $env:REZ_BUILD_PROJECT_NAME
$BinaryDir = Join-Path $env:REZ_BUILD_PATH $ProjectName
$VendorVersion = $env:REZ_BUILD_PROJECT_VENDOR_VERSION
$PackageName = $env:REZ_BUILD_PROJECT_PACKAGE_NAME
$InstallDir = (Join-Path $env:REZ_BUILD_INSTALL_PATH $ProjectName)

Write-Host "PackageName: ${PackageName}" -ForegroundColor "Cyan"
Write-Host "VendorVersion: ${VendorVersion}" -ForegroundColor "Cyan"

if (!(Test-Path $BinaryDir)) {
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "winget"
    $pinfo.RedirectStandardError = $true
    $pinfo.RedirectStandardOutput = $false
    $pinfo.UseShellExecute = $false
    $pinfo.ArgumentList.Add("install")
    $pinfo.ArgumentList.Add($PackageName)
    $pinfo.ArgumentList.Add("--silent")
    $pinfo.ArgumentList.Add("--version")
    $pinfo.ArgumentList.Add($VendorVersion)
    $pinfo.ArgumentList.Add("--location")
    $pinfo.ArgumentList.Add("${BinaryDir}")
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $pinfo
    $process.Start() | Out-Null
    $process.WaitForExit()
    Write-Host "exit code: " + $process.ExitCode
}
else
{
    Write-Host "BinaryDir: ${BinaryDir} exists, skipping build." -ForegroundColor "Yellow"
}

if (!($env:REZ_BUILD_INSTALL -eq "1")) {
    Write-Host "Nothing more to do. Use 'rez-build -i' to install." -ForegroundColor "Green"
    Exit 0
}

Write-Host "Installing..." -ForegroundColor "Green"

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}
if (Test-Path $ProjectName) {
    Copy-Item -Path $ProjectName -Destination $InstallDir -Recurse
}
