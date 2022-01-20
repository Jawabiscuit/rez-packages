# vs Package

A rez package for Windows that contains the Visual Studio core IDE and a minimal set of build tools for building C/C++ as well as other rez packages that make use of the cmake build generator.

All that is necessary to `rez build` is to download the appropriate version (15.9) of [vs_Community.exe](https://my.visualstudio.com/Downloads?q=Visual%20Studio%202017), rename it to vs_Community_2017.exe and put it in `.\src`.

Before running `rez build -i` for the very first time, be sure to copy Response.json and rename it to CustomInstall.json for the unattended installation.

## Visual Studio Installation Details

Information below is about build tools, but it is still applicable to using the installer to install vs.

* Visual Studio Build Tools 2019 Silent Install
  * [How-to guide](https://silentinstallhq.com/visual-studio-build-tools-2019-silent-install-how-to-guide/)
  * `vs_BuildTools.exe --layout .\vs_BuildTools`
  * Basic command to extract setup files
  * Note: That command will create a complete layout directory and take a very long time
  * To create a partial layout then follow
    * [Configure the contents of a network layout](https://docs.microsoft.com/en-us/visualstudio/install/create-a-network-installation-of-visual-studio?view=vs-2022#configure-the-contents-of-a-network-layout) 
* [Bootstrapper commands and command-line parameters](https://docs.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio?view=vs-2022#bootstrapper-commands-and-command-line-parameters)
* [Command line parameter examples - Install using --installPath](https://docs.microsoft.com/en-us/visualstudio/install/command-line-parameter-examples?view=vs-2022#install-using---installpath)
* [Workload: Desktop development with C++](https://docs.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools?view=vs-2022&preserve-view=true#desktop-development-with-c)
  * Microsoft.VisualStudio.Component.Windows10SDK
  * Microsoft.VisualStudio.Component.Windows10SDK.19041
  * Microsoft.VisualStudio.Component.VC.CMake.Project
  * Microsoft.VisualStudio.Component.VC.Modules.x86.x64
* [Workload: MSBuild Tools](https://docs.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools?view=vs-2022&preserve-view=true#msbuild-tools)
  * Microsoft.VisualStudio.Workload.MSBuildTools
* [Automated installation using a response file](https://docs.microsoft.com/en-us/visualstudio/install/automated-installation-with-response-file)
  * [Example customized layout response file content](https://docs.microsoft.com/en-us/visualstudio/install/automated-installation-with-response-file?view=vs-2022#example-customized-layout-response-file-content)