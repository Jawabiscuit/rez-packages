# vs Package

A rez package for Windows that contains the Visual Studio core IDE and a minimal set of build tools for building C/C++ as well as other rez packages that make use of the cmake build generator.

All that is necessary to `rez build` is to download the appropriate version (15.9) of [vs_Community.exe](https://my.visualstudio.com/Downloads?q=Visual%20Studio%202017), rename it to vs_Community_2017.exe and put it in `.\src`.

## Visual Studio Installation Details

Note: Some information below is about installing build tools, but it is still applicable to Visual Studio.

* Visual Studio Build Tools 2019 Silent Install
  * [How-to guide](https://silentinstallhq.com/visual-studio-build-tools-2019-silent-install-how-to-guide/)
  * `vs_BuildTools.exe --layout .\vs_BuildTools`
  * Basic command to extract setup files
  * Note: That command will create a complete layout directory and take a very long time
  * To create a partial layout then follow
    * [Configure the contents of a network layout](https://docs.microsoft.com/en-us/visualstudio/install/create-a-network-installation-of-visual-studio?view=vs-2022#configure-the-contents-of-a-network-layout) 
* [Bootstrapper commands and command-line parameters](https://docs.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio?view=vs-2022#bootstrapper-commands-and-command-line-parameters)
* [Command line parameter examples - Install using --installPath](https://docs.microsoft.com/en-us/visualstudio/install/command-line-parameter-examples?view=vs-2017#install-using---installpath)
* [Workload: Desktop development with C++](https://docs.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-build-tools?view=vs-2017&preserve-view=true#desktop-development-with-c)
  * Microsoft.Component.MSBuild
  * Microsoft.VisualStudio.Component.VC.CMake.Project
  * Microsoft.VisualStudio.Component.VC.CoreIde
  * Microsoft.VisualStudio.Component.VC.Tools.x86.x64
  * Microsoft.VisualStudio.Component.Windows10SDK.17763
* [Workload: Visual Studio Core Editor](https://docs.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-community?view=vs-2017#visual-studio-core-editor-included-with-visual-studio-community-2017)
* [Automated installation using a response file](https://docs.microsoft.com/en-us/visualstudio/install/automated-installation-with-response-file)
  * [Example customized layout response file content](https://docs.microsoft.com/en-us/visualstudio/install/automated-installation-with-response-file?view=vs-2017#example-customized-layout-response-file-content)