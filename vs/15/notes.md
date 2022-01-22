
__Building__

All that is necessary to `rez build` is to download the appropriate version (15.9) of [vs_Community.exe](https://my.visualstudio.com/Downloads?q=Visual%20Studio%202017), rename it to vs_Community_2017.exe and put it in `.\src`.

Before running `rez build -i` for the very first time, be sure to copy Response.json to the root package directory and rename it to CustomInstall.json. Edit that file before running the unattended installation.

```json
    "includeRecommended": false,
    "includeOptional": false,
    "quiet": true,
    "nocache": true,
    "norestart": true,
```