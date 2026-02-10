@echo off
setlocal enabledelayedexpansion

for %%f in (*.MP3) do (
    echo Renaming: %%f
    ren "%%f" "%%~nf.mp3"
)

echo.
echo Tum dosyalar .mp3 yapildi.
pause
