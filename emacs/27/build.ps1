# Silencing progress to make downloads faster
$ProgressPreference = "SilentlyContinue"

if (!(Test-Path ".\emacs-build")) {
    git clone "git@github.com:Jawabiscuit/emacs-build.git"
}

if (!(Test-Path ".\emacs-build\zips")) {
    Push-Location "emacs-build"
    & .\emacs-build.cmd --slim --clone --deps --build --pack-all
    Pop-Location
}

if (!($env:REZ_BUILD_INSTALL -eq "1")) {
    Write-Host "Nothing more to do. Use 'rez-build -i' to install."
    Exit 0
}

Write-Host "Installing..." -ForegroundColor "Green"

if (Test-Path ".\emacs-build\zips") {
    Push-Location ".\emacs-build\zips"
    if (Test-Path "emacs-master-x86_64-full.zip") {
        Expand-Archive "emacs-master-x86_64-full.zip" -DestinationPath $env:REZ_BUILD_INSTALL_PATH -Force
    }
    Pop-Location
}