#!/usr/bin/env python3
"""
Test script for Stock Predictor
Demonstrates various usage examples with different stocks
"""

import subprocess
import sys
from datetime import datetime, timedelta

def run_command(cmd):
    """Run a command and display output"""
    print(f"\n{'='*70}")
    print(f"Running: {cmd}")
    print('='*70)
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    return result.returncode

def main():
    print("Stock Predictor - Test Examples")
    print("="*70)
    
    # Check if packages are installed
    try:
        import yfinance, sklearn, pandas, numpy
        print("✓ All required packages are installed\n")
    except ImportError as e:
        print(f"✗ Missing package: {e}")
        print("\nPlease install with: pip install yfinance scikit-learn pandas numpy")
        sys.exit(1)
    
    future_30 = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    future_60 = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
    future_90 = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    
    examples = [
        {
            "name": "Example 1: Demo Mode (NVDA, 30 days ahead)",
            "cmd": "python stock_predictor.py --demo"
        },
        {
            "name": "Example 2: Apple Stock Prediction (60 days)",
            "cmd": f"python stock_predictor.py AAPL {future_60}"
        },
        {
            "name": "Example 3: Tesla with Visualization (90 days)",
            "cmd": f"python stock_predictor.py TSLA {future_90} --visualize"
        },
        {
            "name": "Example 4: Microsoft with 2 years of data",
            "cmd": f"python stock_predictor.py MSFT {future_30} --days 730"
        },
        {
            "name": "Example 5: Google with 500 days of data + Visualization",
            "cmd": f"python stock_predictor.py GOOGL {future_60} --days 500 --visualize"
        },
        {
            "name": "Example 6: Test Invalid Ticker (should show error)",
            "cmd": f"python stock_predictor.py INVALIDTICKER {future_30}"
        },
        {
            "name": "Example 7: Test Too Many Days (should show error)",
            "cmd": f"python stock_predictor.py AAPL {future_30} --days 50000"
        },
        {
            "name": "Example 8: Test Too Few Days (should show error)",
            "cmd": f"python stock_predictor.py AAPL {future_30} --days 30"
        }
    ]
    
    print("\nAvailable examples:")
    for i, ex in enumerate(examples, 1):
        print(f"\n{i}. {ex['name']}")
        print(f"   {ex['cmd']}")
    
    print("\n" + "="*70)
    choice = input("\nEnter example number (1-8), 'all' to run all, or 'q' to quit: ").strip()
    
    if choice.lower() == 'q':
        print("Exiting...")
        return
    
    if choice.lower() == 'all':
        for ex in examples:
            print(f"\n\n{'#'*70}")
            print(f"# {ex['name']}")
            print(f"{'#'*70}")
            run_command(ex['cmd'])
            input("\nPress Enter to continue to next example...")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                run_command(examples[idx]['cmd'])
            else:
                print("Invalid choice!")
        except ValueError:
            print("Invalid input!")

if __name__ == '__main__':
    main()
