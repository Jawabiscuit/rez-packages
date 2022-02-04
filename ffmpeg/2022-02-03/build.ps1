$Zip_File = "$env:REZ_BUILD_SOURCE_PATH\src\$env:REZ_BUILD_PROJECT_NAME-$env:REZ_BUILD_PROJECT_VERSION.7z"

# Get-ChildItem Env: | Sort-Object Name

if (!(Test-Path ".\$env:REZ_BUILD_PROJECT_NAME-$env:REZ_BUILD_PROJECT_VERSION")) {
    Expand-7Zip -ArchiveFileName $Zip_File -TargetPath .
    Get-ChildItem -Directory . | ForEach-Object {
        Rename-Item $_ -NewName "$env:REZ_BUILD_PROJECT_NAME-$env:REZ_BUILD_PROJECT_VERSION"
    }
}

if (!($env:REZ_BUILD_INSTALL -eq "1")) {
    Write-Host "Nothing more to do. Use 'rez-build -i' to install."
    Exit 0
}

Write-Host "Installing..." -ForegroundColor "Green"

Push-Location ".\$env:REZ_BUILD_PROJECT_NAME-$env:REZ_BUILD_PROJECT_VERSION"

Get-ChildItem -Directory . | Where-Object {
    $_.Name -like "bin" -or
    $_.Name -like "doc" -or
    $_.Name -like "presets"
} | ForEach-Object {
    Copy-Item -Path $_ -Destination $env:REZ_BUILD_INSTALL_PATH -Recurse -Force
}

Pop-Location