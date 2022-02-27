# TBB Rez Package

(oneAPI Threading Building Blocks)[https://github.com/oneapi-src/oneTBB]

TBB is also required to build OpenVDB.


Version 2018 Update 6 (VFX Reference Platform CY2019).

https://github.com/oneapi-src/oneTBB/releases/tag/2018_U6
Get the source code zip (not the Windows specific 'tbb-2020.2-win.zip').


- Extract the archive
- Go to 'build' directory
- Copy vs2013 directory to vs2017
- Open 'makefile.sln' in vs2017
  - If using my rez package: `rez env vs-15 -- devenv .\src\oneTBB-2018_U6\build\vs2019\makefile.sln`
  => Convert the VS solution as well as the VC projects
- Select config (x64|Release)
- Build solution
(could be done with command line)

To use the library:
- `rez build -i`
- `rez env tbb` or `rez env tbb-2018`
