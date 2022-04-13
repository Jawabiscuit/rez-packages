$ProjectName = $env:REZ_BUILD_PROJECT_NAME
$ProjectVersion = $env:REZ_BUILD_PROJECT_VERSION
$PackageName = $env:REZ_BUILD_PROJECT_PACKAGE_NAME
$InstallDir = $env:REZ_BUILD_INSTALL_PATH
$MayaInstallDir = $env:REZ_BUILD_MAYA_INSTALL_PATH
$SourceDir = $env:REZ_BUILD_SOURCE_PATH
$ExeDirectory = "$env:REZ_BUILD_SOURCE_PATH\rel"

Write-Host "PackageName: ${PackageName}" -ForegroundColor "Cyan"
Write-Host "ProjectVersion: ${ProjectVersion}" -ForegroundColor "Cyan"
Write-Host "InstallDir: ${InstallDir}" -ForegroundColor "Cyan"
Write-Host "MayaInstallDir: ${MayaInstallDir}" -ForegroundColor "Cyan"

if (!(Test-Path $MayaInstallDir)) {
    Get-ChildItem -File $ExeDirectory | Where-Object {
        $_.Name -like "*.exe"
    } | ForEach-Object {
        Write-Host "Installing $_" -ForegroundColor Green
        Start-Process -Wait (Join-Path $ExeDirectory $_.Name) -ArgumentList "/S" -PassThru
    }
}
else
{
    Write-Host "Maya Install Dir: ${MayaInstallDir} exists, skipping Maya installation." -ForegroundColor "Yellow"
}

if (!($env:REZ_BUILD_INSTALL -eq "1")) {
    Write-Host "Nothing more to do. Use 'rez-build -i' to install." -ForegroundColor "Green"
    Exit 0
}

Write-Host "Installing package..." -ForegroundColor "Green"

Get-ChildItem -Directory $SourceDir | Where-Object {
    $_.Name -like "Invoke-Maya"
} | ForEach-Object {
    Copy-Item -Path $_ -Destination (Join-Path $InstallDir $Name) -Recurse -Force
}

Get-ChildItem -File $SourceDir | Where-Object {
    $_.Name -like "*ColorManagement.xml"
} | ForEach-Object {
    Copy-Item -Path $_ -Destination (Join-Path $InstallDir $Name) -Force
}