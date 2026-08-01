@echo off
echo === MasterplanOptimiserV3 Testing Setup ===
echo.

echo Creating isolated Desktop and Server Python environments...
python tools\setup_test_env.py all
if errorlevel 1 exit /b %errorlevel%

echo.
echo Installing Node.js dependencies...
call npm install

echo.
echo === Setup complete! ===
echo.
echo Run server backend tests:   .venv-server\Scripts\python -m pytest server_backend/ -v
echo Run desktop backend tests:  .venv-desktop\Scripts\python -m pytest desktop_backend/ -v
echo Run server frontend tests:  npx vitest run --config vitest.config.server.ts
echo Run desktop frontend tests: npx vitest run --config vitest.config.desktop.ts
echo Run all frontend tests:     npm run test:all
