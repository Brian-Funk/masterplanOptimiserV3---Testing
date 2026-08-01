@echo off
echo === Desktop Tests ===
echo.

echo [1/2] Desktop Backend (Python)
.venv-desktop\Scripts\python -m pytest desktop_backend/ -v --tb=short
if errorlevel 1 exit /b %errorlevel%
echo.

echo [2/2] Desktop Frontend (Vitest)
call npm run test:desktop
