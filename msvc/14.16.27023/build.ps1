$Exe_File = "$env:REZ_BUILD_SOURCE_PATH\rel\vs_BuildTools.exe"

# Extract the setup files
if (!(Test-Path ".\vs_BuildTools\Response.json")) {
    if (Test-Path $Exe_File) {
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = $Exe_File
        $pinfo.RedirectStandardError = $true
        $pinfo.RedirectStandardOutput = $false
        $pinfo.UseShellExecute = $false
        $pinfo.ArgumentList.Add("--quiet")
        $pinfo.ArgumentList.Add("--layout")
        $pinfo.ArgumentList.Add(".\vs_BuildTools")
        $pinfo.ArgumentList.Add("--add")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Workload.MSBuildTools")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Workload.VCTools")
        $pinfo.ArgumentList.Add("Microsoft.VisualStudio.Component.VC.CMake.Project")
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

if (Test-Path ".\vs_BuildTools") {
    Copy-Item -Path "$env:REZ_BUILD_SOURCE_PATH\CustomInstall.json" -Destination ".\vs_BuildTools\" -Force
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "$env:REZ_BUILD_PATH\vs_BuildTools\vs_setup.exe"
    $pinfo.RedirectStandardError = $true
    $pinfo.RedirectStandardOutput = $true
    $pinfo.UseShellExecute = $false
    $pinfo.ArgumentList.Add("--installPath")
    $pinfo.ArgumentList.Add("$env:REZ_BUILD_INSTALL_PATH\vs_BuildTools")
    $pinfo.ArgumentList.Add("--in")
    $pinfo.ArgumentList.Add(".\vs_BuildTools\CustomInstall.json")
    $pinfo.ArgumentList.Add("--wait")
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $pinfo
    $process.Start() | Out-Null
    $process.WaitForExit()
    Write-Host "exit code: " + $process.ExitCode
}