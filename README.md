# Stock Price Predictor

A Python program that downloads historical stock data from Yahoo Finance, trains a regression model, and predicts future stock prices for any publicly traded stock.

## Installation

### Step 1: Install Required Packages

```bash
pip install yfinance scikit-learn pandas numpy
```

### Step 2: Download the Scripts

Save the `src/` and `tests/` directories to your computer.

## Quick Start

### Option 1: Demo Mode (Easiest)
```bash
python src/stock_predictor.py --demo
```
This predicts NVDA stock price 30 days from now with visualization.

### Option 2: Predict Any Stock
```bash
python src/stock_predictor.py AAPL 2026-03-15
python src/stock_predictor.py TSLA 2026-04-01 --days 730
```

### Option 3: Run Interactive Examples
```bash
python tests/test_predictor.py
```

## Usage

### Basic Syntax
```bash
python src/stock_predictor.py <TICKER> <YYYY-MM-DD> [OPTIONS]
```

**Required Arguments:**
- `TICKER` - Stock ticker symbol (e.g., AAPL, GOOGL, MSFT, TSLA, NVDA)
- `YYYY-MM-DD` - Target date for prediction (must be in the future)

**Optional Arguments:**
- `--days N` - Number of historical days to use (default: 365, min: 60, max: 9125)
- `--visualize` - Show ASCII chart visualization
- `--demo` - Run demo mode with NVDA (skips ticker and date requirements)

## Usage Examples

### Different Stocks
```bash
# Apple
python src/stock_predictor.py AAPL 2026-03-15

# Tesla with visualization
python src/stock_predictor.py TSLA 2026-04-01 --visualize

# Microsoft with 2 years of data
python src/stock_predictor.py MSFT 2026-03-20 --days 730

# Google with 500 days and visualization
python src/stock_predictor.py GOOGL 2026-05-01 --days 500 --visualize
```

### Using Different Historical Periods
```bash
# 6 months of data
python src/stock_predictor.py AAPL 2026-03-15 --days 180

# 1 year (default)
python src/stock_predictor.py AAPL 2026-03-15 --days 365

# 2 years
python src/stock_predictor.py AAPL 2026-03-15 --days 730

# 5 years
python src/stock_predictor.py AAPL 2026-03-15 --days 1825
```

## How It Works

### 1. **Data Download**
- Downloads historical NVDA stock data from Yahoo Finance
- Default: past 365 days
- Uses closing prices, volume, and other market data

### 2. **Feature Engineering**
The model creates several technical indicators as features:
- **DayNumber**: Sequential day count (primary trend feature)
- **MA_7**: 7-day moving average
- **MA_30**: 30-day moving average
- **Volume_MA**: 7-day volume moving average
- **Volatility**: 7-day standard deviation of closing price

### 3. **Model Training**
- Uses **Linear Regression** from scikit-learn
- Features are scaled using StandardScaler
- Model learns relationships between technical indicators and price

### 4. **Prediction**
- Calculates days between last known data and target date
- Extrapolates features forward
- Predicts closing price for target date

### 5. **Performance Metrics**
The script reports:
- **R² Score**: How well the model fits training data (closer to 1.0 is better)
- **RMSE**: Root Mean Squared Error in dollars
- **MAE**: Mean Absolute Error in dollars

## Example Output

```
===========================================================================
STOCK PRICE PREDICTION
===========================================================================
Ticker Symbol: AAPL
Target Date: 2026-03-15
Historical Data Period: 365 days
===========================================================================

Step 1: Validating ticker symbol...
✓ Ticker 'AAPL' validated successfully

Step 2: Validating historical data period...
✓ Found 252 days of historical data for 'AAPL'

Step 3: Downloading stock data...
Downloading AAPL stock data from 2025-02-07 to 2026-02-07...
✓ Successfully downloaded 252 days of data for AAPL

Recent AAPL closing prices:
Date
2026-02-03    182.35
2026-02-04    185.20
2026-02-05    183.80
2026-02-06    186.15
2026-02-07    187.50
Name: Close, dtype: float64

Latest close: $187.50 on 2026-02-07

Step 4: Creating features and preparing data...
✓ Created features with 222 data points

Step 5: Training regression model...
Model Performance:
  R² Score: 0.9456
  RMSE: $2.89
  Mean Absolute Error: $2.31
✓ Training complete

Step 6: Making prediction...
✓ Prediction complete

===========================================================================
PREDICTION RESULTS FOR AAPL
===========================================================================
Last known price (2026-02-07): $187.50
Predicted price for 2026-03-15: $194.20
Days ahead: 36
Expected change: +$6.70 (+3.57%)
===========================================================================

⚠️  DISCLAIMER: This is a simple model for educational purposes.
Stock predictions are inherently uncertain. Do not use this for
actual investment decisions without consulting financial advisors.
```

## Error Handling

The program includes comprehensive validation:

### Invalid Ticker Symbol
```bash
$ python src/stock_predictor.py INVALIDTICKER 2026-03-15

Step 1: Validating ticker symbol...
❌ Ticker 'INVALIDTICKER' not found or has no data

Please check:
  - The ticker symbol is correct (e.g., NVDA, AAPL, TSLA)
  - The stock is publicly traded
  - You have internet connection
```

### Too Many Days
```bash
$ python src/stock_predictor.py AAPL 2026-03-15 --days 50000

Step 2: Validating historical data period...
❌ Number of days prior (50000) is too large. Maximum is 9125 days (~25 years).

Recommendations:
  - Use between 60 and 9125 days (60 days to ~25 years)
  - For most stocks, 365-730 days (1-2 years) works well
  - Newer stocks may have limited historical data
```

### Too Few Days
```bash
$ python src/stock_predictor.py AAPL 2026-03-15 --days 30

Step 2: Validating historical data period...
❌ Number of days prior (30) is too small. Minimum is 60 days for meaningful predictions.

Recommendations:
  - Use between 60 and 9125 days (60 days to ~25 years)
  - For most stocks, 365-730 days (1-2 years) works well
  - Newer stocks may have limited historical data
```

### Insufficient Historical Data
```bash
$ python src/stock_predictor.py NEWERCOMPANY 2026-03-15 --days 3650

Step 2: Validating historical data period...
❌ Ticker 'NEWERCOMPANY' only has 450 days of historical data available, 
but 3650 days were requested. Please use a smaller value.
```

### Target Date in Past
```bash
$ python src/stock_predictor.py AAPL 2020-01-01

❌ ERROR: Target date must be in the future
Target date: 2020-01-01
Current date: 2026-02-07
```

## Understanding the Model

### Strengths
- Simple and interpretable
- Uses actual historical data
- Captures general trends
- Fast training and prediction

### Limitations
- **Linear assumption**: Assumes price changes follow linear patterns
- **No market events**: Doesn't account for earnings, news, or market crashes
- **Technical only**: Only uses price/volume data, not fundamentals
- **Extrapolation risk**: Further out predictions are less reliable
- **Simplified features**: Future technical indicators use last known values

### Educational Concepts

This program demonstrates:
1. **API integration**: Using yfinance to fetch real market data
2. **Feature engineering**: Creating meaningful predictors from raw data
3. **Data preprocessing**: Handling missing values and scaling
4. **Supervised learning**: Training a regression model
5. **Model evaluation**: Using R², RMSE, and MAE metrics
6. **Time series prediction**: Forecasting future values

## Improving the Model

For better predictions, consider:

1. **More sophisticated models**: Try Random Forest, XGBoost, or LSTM neural networks
2. **More features**: Add market indices, sector performance, sentiment analysis
3. **Cross-validation**: Split data into train/test sets for validation
4. **Ensemble methods**: Combine multiple models
5. **Market regime detection**: Adjust predictions based on volatility patterns
6. **Fundamental data**: Include earnings, P/E ratio, etc.

## Architecture

The application has two modes: a **standalone CLI** and a **full-stack web app** with an AI chatbot.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Browser (localhost:5173)                      │
│                                                                     │
│  ┌──────────────────────────────────┐  ┌─────────────────────────┐  │
│  │         Plotly.js Chart          │  │      Chat Panel         │  │
│  │                                  │  │                         │  │
│  │  - Historical prices (lines)     │  │  User: "Add TSLA"      │  │
│  │  - 7-day & 30-day MA (dashed)    │  │                         │  │
│  │  - Prediction markers (stars)    │  │  Bot: "Adding TSLA..."  │  │
│  │  - Projection lines (dotted)     │  │  [streaming response]   │  │
│  │  - Range slider for zoom         │  │                         │  │
│  │                                  │  │  ┌───────────────────┐  │  │
│  │  Updates via chart_update events │  │  │ Send message...   │  │  │
│  └──────────────────────────────────┘  │  └───────────────────┘  │  │
│              65% width                 │       35% width         │  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                     SSE Stream │ POST /api/chat
                   (text_delta, │ chart_update,
                    tool_start, │ done)
                                │
┌───────────────────────────────┼─────────────────────────────────────┐
│              FastAPI Backend (localhost:8000)                        │
│                               │                                     │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │                   Claude Tool-Use Loop                        │  │
│  │                                                               │  │
│  │  1. Receive user message                                      │  │
│  │  2. Stream to Claude (claude-sonnet-4-6)                      │  │
│  │  3. Claude decides which tool to call                         │  │
│  │  4. Execute tool, return result to Claude                     │  │
│  │  5. Claude generates natural language response                │  │
│  │  6. Stream everything back as SSE events                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│           │                                                         │
│           │ Tool calls                                              │
│           ▼                                                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              stock_predictor.py (shared core)                 │  │
│  │                                                               │  │
│  │  fetch_stock_data ──► create_features ──► train_model         │  │
│  │        │                                       │              │  │
│  │   Yahoo Finance                        predict_future_price   │  │
│  │   (yfinance API)                               │              │  │
│  │                                          Return prediction    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Endpoints:                                                         │
│    GET  /api/defaults  — startup stocks (NVDA, AAPL)                │
│    POST /api/chat      — SSE streaming chat                         │
│    GET  /api/health    — liveness check                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Frontend (React + Vite)

| Component | Role |
|-----------|------|
| `App.jsx` | Root layout, manages `stocks` state object, loads defaults on mount |
| `StockChart.jsx` | Renders Plotly.js chart with per-stock traces; uses `ResizeObserver` for responsive resizing |
| `ChatPanel.jsx` | Chat UI with streaming text, tool activity indicators, and keyboard shortcuts |
| `api.js` | `fetchDefaults()` and `streamChat()` async generator for SSE consumption |

### Backend (FastAPI)

| Module | Role |
|--------|------|
| `server.py` | FastAPI app with SSE streaming chat endpoint; runs Claude tool-use loop |
| `stock_predictor.py` | Core prediction pipeline shared by CLI, web backend, and agent team |
| `agent_team.py` | Standalone multi-agent pipeline (orchestrator + risk + report agents) |

### Communication Flow

1. **On startup**: Frontend calls `GET /api/defaults` to load NVDA and AAPL chart data
2. **Chat interaction**: Frontend sends `POST /api/chat` with the message history
3. **SSE stream**: Backend streams events back in real-time:
   - `text_delta` — Claude's response text (streamed token by token)
   - `tool_start` — indicates a tool is being called (triggers loading indicator)
   - `chart_update` — contains full stock data payload (triggers chart re-render)
   - `tool_error` — tool execution failed
   - `done` — response complete
4. **Tool execution**: Claude decides which tools to call (`add_stock`, `remove_stock`, `clear_chart`, `get_stock_price`), the backend executes them against `stock_predictor.py`, and feeds results back to Claude for interpretation

### Running the Web App

```bash
# Terminal 1 — Backend
pip install fastapi uvicorn anthropic
cd src && uvicorn server:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Default stocks load automatically; use the chatbot to add more.

## Troubleshooting

### "No module named 'yfinance'"
Run: `pip install yfinance`

### "No data retrieved for NVDA"
- Check your internet connection
- Yahoo Finance may be temporarily unavailable
- Try again in a few minutes

### "Target date must be after..."
- Make sure your target date is in the future
- Use YYYY-MM-DD format exactly

## License

This is educational code provided as-is. Use at your own risk.
