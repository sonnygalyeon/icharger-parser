@echo off
setlocal
if "%~1"=="" (
  echo Usage: run.bat "path\to\log.txt" [more logs or folders]
  exit /b 2
)
python main.py %* -o output
if errorlevel 1 pause
endlocal
