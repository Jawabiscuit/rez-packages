# msvc package

A rez package for Windows that contains the minimal set of Visual Studio build tools for building C/C++ as well as (optionally) other rez packages that make use of the cmake build generator.

All that is necessary to `rez build` is to download the appropriate version of [vs_BuildTools](https://aka.ms/vs/15/release/vs_BuildTools.exe) and put it in `.\rel`.

## :books: Reference

Info about how this packages is constructed.

* Visual Studio Build Tools 2017 Silent Install
  - [How-to guide](https://silentinstallhq.com/visual-studio-build-tools-2017-silent-install-how-to-guide/)
  - `vs_BuildTools.exe --layout .\vs_BuildTools`
    * Basic command to extract setup files
  - Note: That command will create a complete layout directory and take a very long time
  - To create a partial layout then follow
    * [Configure the contents of a network layout](https://learn.microsoft.com/en-us/visualstudio/install/create-a-network-installation-of-visual-studio?view=vs-2022#configure-the-contents-of-a-network-layout)

* Command line parameters
  - [Bootstrapper commands and command-line parameters](https://learn.microsoft.com/en-us/visualstudio/install/use-command-line-parameters-to-install-visual-studio?view=vs-2022#bootstrapper-commands-and-command-line-parameters)

  - [Install using --installPath](https://learn.microsoft.com/en-us/visualstudio/install/command-line-parameter-examples?view=vs-2022#install-using---installpath)

* [Workloads: Desktop development with C++](https://learn.microsoft.com/en-us/previous-versions/visualstudio/visual-studio-2017/install/workload-component-id-vs-build-tools?view=vs-2017&preserve-view=true#desktop-development-with-c)
  - Microsoft.VisualStudio.Workload.MSBuildTools
  - Microsoft.VisualStudio.Workload.VCTools
  - Microsoft.VisualStudio.Component.VC.CMake.Project

* [Workload: MSBuild Tools](https://learn.microsoft.com/en-us/previous-versions/visualstudio/visual-studio-2017/install/workload-component-id-vs-build-tools?view=vs-2017&preserve-view=true#msbuild-tools)
  - Microsoft.VisualStudio.Workload.MSBuildTools

* [Automated installation using a response file](https://learn.microsoft.com/en-us/visualstudio/install/automated-installation-with-response-file)
  - [Example customized layout response file content](https://learn.microsoft.com/en-us/visualstudio/install/automated-installation-with-response-file?view=vs-2022#example-customized-layout-response-file-content)

* Note about VsDevCmd.bat and setting `VS150COMNTOOLS`

  > ...starting from VS 2017 this variable is not set by default any more and looks like a preferable way going forward is running VS 2017 Command Line script during the build ~[source](https://help.appveyor.com/discussions/kb/48-vs2017)

  > It's probably best to get used to using the "Developer Command Prompt" that matches the VS you want to use. ~[source](https://github.com/dotnet/fsharp/issues/1761#issuecomment-261802149)