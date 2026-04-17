@echo off
echo === MasterplanOptimiserV3 Testing Setup ===
echo.

REM Create Python virtual environment
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

echo Installing Python dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo Installing Node.js dependencies...
call npm install

echo.
echo === Setup complete! ===
echo.
echo Run server backend tests:   .venv\Scripts\activate ^&^& pytest server_backend/ -v
echo Run desktop backend tests:  .venv\Scripts\activate ^&^& pytest desktop_backend/ -v
echo Run server frontend tests:  npx vitest run --config vitest.config.server.ts
echo Run desktop frontend tests: npx vitest run --config vitest.config.desktop.ts
echo Run all frontend tests:     npm run test:all
