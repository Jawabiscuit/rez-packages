<#
Invoke-Maya.ps1
Maya alias
#>

Function Invoke-Maya {

    [CmdletBinding()] 
    [Alias('m')]

    Param(
        [string] $File,
        [string] $Script
        # [int] $Option3
    )

    $mayaCmd = "maya"
    $argList = @("-proj", (Get-Location))

    if ($File -ne "") {
        $argList += @("-file", $File)
    }

    if ($Script -ne "") {
        $argList += @("-script", $Script)
    }

    If ($MyInvocation.InvocationName -eq 'm') {
        Write-Host "Launching Maya!" -ForegroundColor Yellow
        Write-Host $mayaCmd $argList
        Start-Process -NoNewWindow $mayaCmd -ArgumentList $argList
    }
    Else {
        Write-Host "Launching Maya..." -ForegroundColor Green
        Write-Host $mayaCmd $argList
        Start-Process -NoNewWindow $mayaCmd -ArgumentList $argList
    }
}
