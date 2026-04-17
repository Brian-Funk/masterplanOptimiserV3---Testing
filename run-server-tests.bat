@echo off
echo === Server Tests ===
echo.

echo [1/2] Server Backend (Python)
call .venv\Scripts\activate.bat
pytest server_backend/ -v --tb=short
echo.

echo [2/2] Server Frontend (Vitest)
call npm run test:server
