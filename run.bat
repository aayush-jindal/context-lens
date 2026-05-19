@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul && py -3 run.py %* & exit /b %ERRORLEVEL%
where python3 >nul 2>nul && python3 run.py %* & exit /b %ERRORLEVEL%
where python >nul 2>nul && python run.py %* & exit /b %ERRORLEVEL%

echo Python 3.9+ is required but was not found on PATH.
exit /b 1
