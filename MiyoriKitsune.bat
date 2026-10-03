@echo off
setlocal
cd /d "%~dp0"
title Miyori Kitsune

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  where python >nul 2>nul && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo [Miyori Kitsune] Python 3 was not found.
  echo Install Python 3.10+ or place a portable Python runtime next to the project.
  pause
  exit /b 1
)

%PYTHON_CMD% core\server.py
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [Miyori Kitsune] Core stopped with error %EXIT_CODE%.
  pause
)

exit /b %EXIT_CODE%
