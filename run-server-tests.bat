@echo off
echo === Server Tests ===
echo.

echo [1/2] Server Backend (Python)
.venv-server\Scripts\python -m pytest server_backend/ -v --tb=short
if errorlevel 1 exit /b %errorlevel%
echo.

echo [2/2] Server Frontend (Vitest)
call npm run test:server
