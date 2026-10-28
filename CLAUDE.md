# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project conventions

### Always use a branch and pull request

Never commit or push directly to `main`. For any change:

1. Create a new branch.
2. Commit the change there.
3. Push the branch.
4. Open a pull request against `main` (e.g. with `gh pr create`).

This repo has an automated AI review workflow
(`.github/workflows/ai-review.yml`) that only runs on pull requests — a
direct push to `main` skips it entirely and gets no review.

## Setup

```bash
bash setup.sh
# or manually:
pip install yfinance scikit-learn pandas numpy plotly anthropic fastapi uvicorn
```

## Running the Web App

Requires two terminals and `ANTHROPIC_API_KEY` in the environment.

```bash
# Terminal 1 — Backend (FastAPI + Claude)
cd src && uvicorn server:app --reload --port 8000

# Terminal 2 — Frontend (React + Vite)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. NVDA and AAPL load by default; use the chatbot to add/remove stocks, get predictions, etc.

## Running the CLI Predictor

```bash
# Demo mode (NVDA, 30 days ahead)
python src/stock_predictor.py --demo

# Single stock prediction
python src/stock_predictor.py AAPL 2026-06-01

# Compare up to 3 stocks with interactive Plotly chart
python src/stock_predictor.py NVDA AAPL 2026-06-01 --days 730 --plot

# Include S&P 500 for comparison
python src/stock_predictor.py TSLA 2026-06-01 --sp500 --plot

# ASCII chart visualization
python src/stock_predictor.py MSFT 2026-06-01 --visualize

# Debug mode (full tracebacks)
python src/stock_predictor.py AAPL 2026-06-01 --debug
```

## Running the Agent Team

```bash
# Must run from the src/ directory so the relative import resolves
cd src
python agent_team.py "What will AAPL be on 2026-08-01?"
```

Requires `ANTHROPIC_API_KEY` in the environment.

## Interactive Test Examples

```bash
python tests/test_predictor.py
```

This is an interactive script (not a test framework) — it prompts for which example to run.

## Architecture

### `src/stock_predictor.py` — Standalone CLI predictor

Pipeline: `fetch_stock_data` → `create_features` → `train_model` → `predict_future_price` → output/plot.

- **Features**: DayNumber, MA_7, MA_30, Volume_MA, Volatility (all derived from closing price and volume)
- **Model**: LinearRegression with StandardScaler. Uses an honest 80/20 chronological train/test split for reported metrics, then refits on the full dataset for the final prediction.
- **Visualization**: `--visualize` prints an ASCII bar chart; `--plot` opens an interactive Plotly chart with hover, zoom, and a range slider. Supports up to 3 tickers simultaneously.
- **Limits**: `--days` must be 60–9125. The last positional arg is always the target date (YYYY-MM-DD); all preceding positional args are ticker symbols.

### `src/server.py` + `frontend/` — Web app with AI chatbot

- **Backend** (`server.py`): FastAPI app with SSE streaming. Runs a Claude tool-use loop with 4 tools: `add_stock`, `remove_stock`, `clear_chart`, `get_stock_price`. `GET /api/defaults` pre-loads NVDA + AAPL on startup. System prompt is built dynamically via `_build_system()` to inject today's date.
- **Frontend** (React + Vite): Split-pane layout — Plotly.js chart (left, 65%) and chat panel (right, 35%). `StockChart.jsx` uses `Plotly.newPlot`/`Plotly.react` directly (not react-plotly.js) with a `ResizeObserver` for responsive sizing. `ChatPanel.jsx` consumes SSE via an async generator in `api.js`.
- **SSE events**: `text_delta` (streamed text), `tool_start` (loading indicator), `chart_update` (add/remove/clear stock data), `tool_error`, `done`.

### `src/agent_team.py` — Multi-agent Claude pipeline

Orchestrates three specialized agents using the Anthropic API (tool_use loop):

1. **Analysis agent** (Python, no LLM): calls `fetch_stock_data` + `create_features` + `train_model` + `predict_future_price` from `stock_predictor.py`. Re-runs the 80/20 eval split internally to extract test metrics since `train_model` only prints them.
2. **Risk agent** (LLM sub-call): classifies prediction risk as low/medium/high based on R², RMSE, and days_ahead thresholds.
3. **Report agent** (LLM sub-call): formats all data into a user-facing summary.

The orchestrator runs a manual `tool_use` loop — it sends the query, dispatches tool calls via `execute_tool`, feeds results back as `tool_result` messages, and repeats until `stop_reason == "end_turn"`.

`agent_team.py` imports from `stock_predictor` using a bare module name, so `src/` must be on `sys.path` (run from `src/` or set `PYTHONPATH=src`).

### Key constraints

- `--days` minimum 60, maximum 9125 (~25 years)
- Up to 3 tickers can be compared at once (enforced in `main()`)
- `--sp500` appends `^GSPC` to the ticker list and counts toward the 3-ticker limit
- Target date must be strictly in the future relative to `datetime.now()`
