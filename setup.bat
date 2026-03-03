@echo off
REM Setup script for Stock Price Predictor (Windows)

echo ================================================
echo Stock Price Predictor - Setup
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.7 or higher from https://www.python.org/
    pause
    exit /b 1
)

python --version
echo.

REM Install required packages
echo Installing required packages...
echo This may take a few minutes...
echo.

pip install yfinance scikit-learn pandas numpy

if errorlevel 1 (
    echo.
    echo ================================================
    echo Installation failed!
    echo ================================================
    echo.
    echo Please try installing manually:
    echo   pip install yfinance scikit-learn pandas numpy
    pause
    exit /b 1
)

echo.
echo ================================================
echo Installation complete!
echo ================================================
echo.
echo You can now run the predictor with any stock:
echo   python src/stock_predictor.py AAPL 2026-03-15
echo   python src/stock_predictor.py TSLA 2026-04-01 --days 730
echo.
echo Or try demo mode:
echo   python src/stock_predictor.py --demo
echo.
echo Or run interactive examples:
echo   python tests/test_predictor.py
echo.
pause
