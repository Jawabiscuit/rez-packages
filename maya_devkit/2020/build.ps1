$Major = $Args[0]
$Minor = $Args[1]
$DoCopy = $Minor = $Args[2]
$Zip_File = "$env:REZ_BUILD_SOURCE_PATH\rel\Autodesk_Maya_${Major}_${Minor}_Update_DEVKIT_Windows.zip"

if (!(Test-Path ".\devkitBase")) {
    Expand-Archive "$Zip_File" -DestinationPath .

    Push-Location ".\devkitBase"

    if ((Test-Path ".\mkspecs")) {
        Push-Location -Path "mkspecs"
        Get-ChildItem . | Where-Object {$_.Name -like "*.zip"} | ForEach-Object {Expand-Archive $_ -DestinationPath .}
        Pop-Location
    }

    if ((Test-Path ".\include")) {
        Push-Location -Path "include"
        Get-ChildItem . | Where-Object {$_.Name -like "*.zip"} | ForEach-Object {Expand-Archive $_ -DestinationPath .}
        Pop-Location
    }

    if (!(Test-Path ".\plug-ins")) {
        New-Item -Path . -Name "plug-ins" -ItemType "directory"
    }

    Pop-Location
}

if (!($env:REZ_BUILD_INSTALL -eq "1")) {
    Write-Host "Nothing more to do. Use 'rez-build -i' to install."
    Exit 0
}

Write-Host "Installing..." -ForegroundColor "Green"

$DevkitLocation = "$env:REZ_BUILD_INSTALL_PATH\devkitBase"
if ($DoCopy -and (Test-Path $DevkitLocation)) {
    Remove-Item $DevkitLocation -Recurse -Force
}
if ($DoCopy) {
    Copy-Item -Path ".\devkitBase" -Destination $env:REZ_BUILD_INSTALL_PATH -Recurse
}

Push-Location $DevkitLocation

if (!(Test-Path ".\qt-bin")) {
    mkdir "qt-bin"
}
Write-Host "Linking Qt tools from Maya" -ForegroundColor "Green"
Get-ChildItem "$env:MAYA_LOCATION\bin" | Where-Object {
    $_.Name -like "moc.exe" -or
    $_.Name -like "rcc.exe" -or
    $_.Name -like "qmake.exe" -or
    $_.Name -like "uic.exe"
} | ForEach-Object {
    New-Item -ItemType SymbolicLink -Path ".\qt-bin" -Name $_.Name -Value $_
}

Pop-Location