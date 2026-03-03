#!/bin/bash
# Setup script for Stock Price Predictor

echo "================================================"
echo "Stock Price Predictor - Setup"
echo "================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.7 or higher from https://www.python.org/"
    exit 1
fi

echo "✓ Python 3 is installed: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "ERROR: pip is not installed!"
    echo "Please install pip: https://pip.pypa.io/en/stable/installation/"
    exit 1
fi

echo "✓ pip is installed"
echo ""

# Install required packages
echo "Installing required packages..."
echo "This may take a few minutes..."
echo ""

pip3 install yfinance scikit-learn pandas numpy || pip install yfinance scikit-learn pandas numpy

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "✓ Installation complete!"
    echo "================================================"
    echo ""
    echo "You can now run the predictor with any stock:"
    echo "  python3 src/stock_predictor.py AAPL 2026-03-15"
    echo "  python3 src/stock_predictor.py TSLA 2026-04-01 --days 730"
    echo ""
    echo "Or try demo mode:"
    echo "  python3 src/stock_predictor.py --demo"
    echo ""
    echo "Or run interactive examples:"
    echo "  python3 tests/test_predictor.py"
    echo ""
else
    echo ""
    echo "================================================"
    echo "✗ Installation failed!"
    echo "================================================"
    echo ""
    echo "Please try installing manually:"
    echo "  pip install yfinance scikit-learn pandas numpy"
    exit 1
fi
