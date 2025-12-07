@echo off
echo ========================================
echo Installing Frontend Dependencies
echo ========================================
echo.

cd frontend

echo Checking Node.js version...
node --version
echo.

echo Installing dependencies...
npm install

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo To start the dev server, run:
echo   cd frontend
echo   npm run dev
echo.
pause
