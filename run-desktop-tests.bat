@echo off
echo === Desktop Tests ===
echo.

echo [1/2] Desktop Backend (Python)
call .venv\Scripts\activate.bat
pytest desktop_backend/ -v --tb=short
echo.

echo [2/2] Desktop Frontend (Vitest)
call npm run test:desktop
