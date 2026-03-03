# Stock Predictor - Quick Reference

## Basic Usage
```bash
python src/stock_predictor.py <TICKER> <DATE> [OPTIONS]
```

## Examples

### Popular Stocks
```bash
# Tech Giants
python src/stock_predictor.py AAPL 2026-03-15    # Apple
python src/stock_predictor.py MSFT 2026-03-15    # Microsoft
python src/stock_predictor.py GOOGL 2026-03-15   # Google
python src/stock_predictor.py AMZN 2026-03-15    # Amazon
python src/stock_predictor.py META 2026-03-15    # Meta/Facebook

# AI & Semiconductors
python src/stock_predictor.py NVDA 2026-03-15    # NVIDIA
python src/stock_predictor.py AMD 2026-03-15     # AMD
python src/stock_predictor.py INTC 2026-03-15    # Intel
python src/stock_predictor.py TSM 2026-03-15     # Taiwan Semiconductor

# Electric Vehicles
python src/stock_predictor.py TSLA 2026-03-15    # Tesla
python src/stock_predictor.py RIVN 2026-03-15    # Rivian
python src/stock_predictor.py F 2026-03-15       # Ford

# Other Popular
python src/stock_predictor.py NFLX 2026-03-15    # Netflix
python src/stock_predictor.py DIS 2026-03-15     # Disney
python src/stock_predictor.py BA 2026-03-15      # Boeing
python src/stock_predictor.py JPM 2026-03-15     # JP Morgan
```

### Options

#### Historical Period (--days)
```bash
# Short term (3 months)
python src/stock_predictor.py AAPL 2026-03-15 --days 90

# Medium term (1 year) - DEFAULT
python src/stock_predictor.py AAPL 2026-03-15 --days 365

# Long term (2 years)
python src/stock_predictor.py AAPL 2026-03-15 --days 730

# Very long term (5 years)
python src/stock_predictor.py AAPL 2026-03-15 --days 1825
```

#### Visualization (--visualize)
```bash
# Show ASCII chart
python src/stock_predictor.py TSLA 2026-04-01 --visualize
```

#### Demo Mode (--demo)
```bash
# Quick test with NVDA, 30 days ahead
python src/stock_predictor.py --demo
```

### Combined Options
```bash
# Tesla with 2 years of data and visualization
python src/stock_predictor.py TSLA 2026-04-01 --days 730 --visualize

# Apple with 6 months of data
python src/stock_predictor.py AAPL 2026-03-20 --days 180 --visualize
```

## Validation Limits

| Parameter | Minimum | Maximum | Recommended |
|-----------|---------|---------|-------------|
| Days Prior | 60 | 9,125 (~25 years) | 365-730 (1-2 years) |
| Prediction Days Ahead | 1 | No limit* | 30-90 days |

*Further predictions are less reliable

## Common Errors

### Error: Invalid Ticker
**Problem:** Ticker symbol doesn't exist or is misspelled
**Solution:** Check ticker symbol on Yahoo Finance or Google

### Error: Too few days
**Problem:** --days value is less than 60
**Solution:** Use at least 60 days: `--days 60`

### Error: Too many days
**Problem:** --days value is more than 9,125
**Solution:** Use maximum 9,125 days: `--days 9125`

### Error: Insufficient data
**Problem:** Stock doesn't have enough historical data
**Solution:** Reduce --days value or choose older stock

### Error: Target date in past
**Problem:** Date provided is not in the future
**Solution:** Use a future date in YYYY-MM-DD format

## Tips for Better Predictions

1. **Use appropriate historical period:**
   - Stable companies: 1-2 years (365-730 days)
   - Volatile stocks: 6-12 months (180-365 days)
   - New companies: Use all available data

2. **Choose realistic prediction windows:**
   - Short term (1-30 days): More reliable
   - Medium term (30-90 days): Moderate reliability
   - Long term (90+ days): Less reliable

3. **Consider multiple predictions:**
   - Run predictions with different historical periods
   - Compare results to gauge confidence
   - Example: Try --days 180, 365, and 730

4. **Monitor model performance:**
   - R² Score closer to 1.0 = better fit
   - Lower RMSE = more accurate predictions
   - Compare predictions across different stocks

## Interactive Mode

For a guided experience with multiple examples:
```bash
python tests/test_predictor.py
```

This provides 8 pre-configured examples including:
- Demo mode
- Various stock predictions
- Error handling demonstrations
- Different historical periods

## Finding Stock Tickers

Popular sources:
- Yahoo Finance: https://finance.yahoo.com
- Google Finance: https://www.google.com/finance
- Company investor relations pages

Common ticker formats:
- US stocks: Usually 1-5 letters (AAPL, TSLA, MSFT)
- International: May include exchange suffix (TSM, BABA)
- ETFs: 2-4 letters (SPY, QQQ, VTI)
