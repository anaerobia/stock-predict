"""FastAPI backend for the stock predictor chatbot.

Provides:
  - GET  /api/defaults  — chart data for default startup stocks (NVDA, AAPL)
  - POST /api/chat      — SSE streaming Claude tool-use loop
  - GET  /api/health    — liveness check

Run:
    cd src && uvicorn server:app --reload --port 8000

Requires: fastapi uvicorn anthropic (in addition to the stock_predictor deps)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator

import anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Allow importing from this same src/ directory
sys.path.insert(0, os.path.dirname(__file__))
from stock_predictor import (
    create_features,
    fetch_stock_data,
    predict_future_price,
    train_model,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Stock Predictor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = anthropic.AsyncAnthropic()
MODEL = "claude-sonnet-4-6"

DEFAULT_TICKERS = ["NVDA", "AAPL"]

# ---------------------------------------------------------------------------
# Claude system prompt + tools
# ---------------------------------------------------------------------------

def _build_system() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    default_target = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    return (
        f"You are a helpful stock market assistant with access to real-time stock data tools.\n"
        f"\n"
        f"Today's date is {today}.\n"
        f"\n"
        f"You can:\n"
        f"- Add stocks to an interactive chart with price predictions (add_stock)\n"
        f"- Remove stocks from the chart (remove_stock)\n"
        f"- Clear all stocks from the chart (clear_chart)\n"
        f"- Look up a stock's current or predicted price (get_stock_price)\n"
        f"\n"
        f"When a user mentions a stock ticker or asks for a prediction, call the appropriate tool immediately.\n"
        f"If no target date is specified for a prediction, use {default_target} (30 days from today).\n"
        f"Always interpret results in plain language and note that predictions are educational model estimates,\n"
        f"not financial advice. Keep responses concise."
    )

TOOLS: list[dict[str, Any]] = [
    {
        "name": "add_stock",
        "description": (
            "Fetch historical stock data, train a regression model, and add the stock "
            "to the interactive chart with a predicted price for the target date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. AAPL, NVDA, TSLA)",
                },
                "target_date": {
                    "type": "string",
                    "description": "Prediction target date in YYYY-MM-DD format",
                },
                "days": {
                    "type": "integer",
                    "description": "Historical days to use for training (60–9125, default 365)",
                    "default": 365,
                },
            },
            "required": ["ticker", "target_date"],
        },
    },
    {
        "name": "remove_stock",
        "description": "Remove a stock ticker from the chart.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker to remove"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "clear_chart",
        "description": "Remove all stocks from the chart.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_stock_price",
        "description": (
            "Get a stock's most recent closing price (for today/past dates) "
            "or a model-predicted price (for future dates)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format",
                },
            },
            "required": ["ticker", "date"],
        },
    },
]

# ---------------------------------------------------------------------------
# Synchronous tool implementations (executed in a thread pool)
# ---------------------------------------------------------------------------


def _sync_add_stock(ticker: str, target_date: str, days: int = 365) -> dict[str, Any]:
    """Fetch data, train model, return full chart payload + summary."""
    raw_df = fetch_stock_data(ticker.upper(), days)
    featured = create_features(raw_df)
    model, scaler, training_data = train_model(featured)

    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    predicted_price, days_ahead = predict_future_price(model, scaler, training_data, target_dt)

    return {
        "ticker": ticker.upper(),
        "dates": [d.strftime("%Y-%m-%d") for d in training_data.index],
        "prices": [round(float(p), 2) for p in training_data["Close"].values],
        "ma7": [round(float(v), 2) for v in training_data["MA_7"].values],
        "ma30": [round(float(v), 2) for v in training_data["MA_30"].values],
        "predicted_price": round(float(predicted_price), 2),
        "target_date": target_date,
        "current_price": round(float(training_data["Close"].iloc[-1]), 2),
        "last_date": training_data.index[-1].strftime("%Y-%m-%d"),
        "days_ahead": days_ahead,
    }


def _sync_get_price(ticker: str, date: str) -> dict[str, Any]:
    target_dt = datetime.strptime(date, "%Y-%m-%d")
    raw_df = fetch_stock_data(ticker.upper(), 365)
    featured = create_features(raw_df)

    if target_dt <= datetime.now():
        return {
            "ticker": ticker.upper(),
            "type": "actual",
            "price": round(float(featured["Close"].iloc[-1]), 2),
            "date": featured.index[-1].strftime("%Y-%m-%d"),
        }

    model, scaler, training_data = train_model(featured)
    predicted, days_ahead = predict_future_price(model, scaler, training_data, target_dt)
    return {
        "ticker": ticker.upper(),
        "type": "predicted",
        "price": round(float(predicted), 2),
        "date": date,
        "days_ahead": days_ahead,
        "current_price": round(float(training_data["Close"].iloc[-1]), 2),
    }


# ---------------------------------------------------------------------------
# Async tool dispatcher
# ---------------------------------------------------------------------------


async def _execute_tool(
    name: str, tool_input: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    """Execute a tool and return (result_json, optional_chart_event)."""
    if name == "add_stock":
        chart_data = await asyncio.to_thread(
            _sync_add_stock,
            tool_input["ticker"],
            tool_input["target_date"],
            tool_input.get("days", 365),
        )
        chart_event = {"action": "add", "ticker": chart_data["ticker"], "data": chart_data}
        # Strip heavy arrays from the summary returned to Claude
        summary = {k: v for k, v in chart_data.items() if k not in ("dates", "prices", "ma7", "ma30")}
        return json.dumps(summary), chart_event

    if name == "remove_stock":
        ticker = tool_input["ticker"].upper()
        return json.dumps({"removed": ticker}), {"action": "remove", "ticker": ticker}

    if name == "clear_chart":
        return json.dumps({"cleared": True}), {"action": "clear"}

    if name == "get_stock_price":
        result = await asyncio.to_thread(_sync_get_price, tool_input["ticker"], tool_input["date"])
        return json.dumps(result), None

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def _sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


async def _stream_chat(messages: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
    """Run the Claude tool-use loop and yield SSE-formatted events."""
    history = list(messages)

    while True:
        tool_uses: list[dict[str, Any]] = []
        current_tool_id: str | None = None
        current_tool_name: str | None = None
        input_acc = ""

        async with _client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=_build_system(),
            tools=TOOLS,
            messages=history,
        ) as stream:
            async for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    blk = event.content_block
                    if blk.type == "tool_use":
                        current_tool_id = blk.id
                        current_tool_name = blk.name
                        input_acc = ""
                        yield _sse("tool_start", {"name": blk.name})

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield _sse("text_delta", {"content": delta.text})
                    elif delta.type == "input_json_delta" and current_tool_id:
                        input_acc += delta.partial_json

                elif etype == "content_block_stop":
                    if current_tool_id:
                        parsed = json.loads(input_acc) if input_acc else {}
                        tool_uses.append(
                            {"id": current_tool_id, "name": current_tool_name, "input": parsed}
                        )
                        current_tool_id = None
                        current_tool_name = None
                        input_acc = ""

            final_message = await stream.get_final_message()

        history.append({"role": "assistant", "content": final_message.content})

        if final_message.stop_reason != "tool_use" or not tool_uses:
            yield _sse("done", {})
            break

        tool_results = []
        for tu in tool_uses:
            try:
                result_json, chart_event = await _execute_tool(tu["name"], tu["input"])
                if chart_event:
                    yield _sse("chart_update", chart_event)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": result_json,
                    }
                )
            except Exception as exc:
                yield _sse("tool_error", {"name": tu["name"], "error": str(exc)})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": f"Error: {exc}",
                        "is_error": True,
                    }
                )

        history.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> StreamingResponse:
    """Streaming SSE chat endpoint with Claude tool-use loop."""
    return StreamingResponse(
        _stream_chat(req.messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/defaults")
async def get_defaults() -> list[dict[str, Any]]:
    """Return chart data for the default startup stocks (fetched in parallel)."""
    target_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    async def _fetch(ticker: str) -> dict[str, Any] | None:
        try:
            return await asyncio.to_thread(_sync_add_stock, ticker, target_date, 365)
        except Exception as exc:
            print(f"[defaults] Failed to load {ticker}: {exc}")
            return None

    results = await asyncio.gather(*[_fetch(t) for t in DEFAULT_TICKERS])
    return [r for r in results if r is not None]


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
