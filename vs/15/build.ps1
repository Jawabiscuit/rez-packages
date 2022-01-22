$Exe_File = "$env:REZ_BUILD_SOURCE_PATH\src\vs_Community_2017.exe"

# Extract the setup files
if (!(Test-Path ".\vs_Community_2017\Response.json")) {
    if (Test-Path $Exe_File) {
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = $Exe_File
        $pinfo.RedirectStandardError = $true
        $pinfo.RedirectStandardOutput = $false
        $pinfo.UseShellExecute = $false
        $pinfo.ArgumentList.Add("--quiet")
        $pinfo.ArgumentList.Add("--layout")
        $pinfo.ArgumentList.Add(".\vs_Community_2017")
        $pinfo.ArgumentList.Add("--add")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Workload.NativeDesktop")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Component.VC.Tools.x86.x64")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Component.VC.CMake.Project")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Component.Windows10SDK.17763")
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $pinfo
        $process.Start() | Out-Null
        $process.WaitForExit()
        Write-Host "exit code: " + $process.ExitCode
    }
}

if (!($env:REZ_BUILD_INSTALL -eq "1")) {
    Write-Host "Nothing more to do. Use 'rez-build -i' to install."
    Exit 0
}

Write-Host "Installing..." -ForegroundColor "Green"

if (Test-Path ".\vs_Community_2017") {
    Copy-Item -Path "$env:REZ_BUILD_SOURCE_PATH\CustomInstall.json" -Destination ".\vs_Community_2017\" -Force
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "$env:REZ_BUILD_PATH\vs_Community_2017\vs_setup.exe"
    $pinfo.RedirectStandardError = $true
    $pinfo.RedirectStandardOutput = $true
    $pinfo.UseShellExecute = $false
    $pinfo.ArgumentList.Add("--installPath")
    $pinfo.ArgumentList.Add("$env:REZ_BUILD_INSTALL_PATH\vs_Community_2017")
    $pinfo.ArgumentList.Add("--in")
    $pinfo.ArgumentList.Add(".\vs_Community_2017\CustomInstall.json")
    $pinfo.ArgumentList.Add("--wait")
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $pinfo
    $process.Start() | Out-Null
    $process.WaitForExit()
    Write-Host "exit code: " + $process.ExitCode
}