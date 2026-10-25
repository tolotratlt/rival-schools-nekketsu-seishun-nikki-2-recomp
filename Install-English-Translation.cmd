@echo off
rem Builds the English translation mod from your own disc image.
rem Run it after the first "Generate & rebuild", with the disc selected in the launcher.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required ^(the same one the setup wizard uses^).
  pause
  exit /b 1
)
python tools\localization\build_english_mod.py %*
pause
