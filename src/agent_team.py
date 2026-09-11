"""Multi-agent Claude team for stock price prediction queries.

Orchestrates a pipeline of specialized agents:
  - Data + Analysis agent (Python): fetches data, trains model, predicts price
  - Risk agent (LLM): evaluates prediction confidence
  - Report agent (LLM): formats the final user-facing summary

Usage:
    python src/agent_team.py "What will AAPL be on 2026-08-01?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Any

import anthropic
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, r2_score

from stock_predictor import (
    create_features,
    fetch_stock_data,
    predict_future_price,
    train_model,
)

MODEL = "claude-sonnet-4-6"

ORCHESTRATOR_SYSTEM = """You are a stock analysis orchestrator. When the user asks about a stock price prediction, you must:
1. Call analyze_stock with the ticker symbol, target date (YYYY-MM-DD), and optional days of history.
2. Call assess_risk with the prediction metrics from step 1.
3. Call generate_report with all gathered information to produce the final response.

Always complete all three steps before responding to the user. Extract ticker symbols and dates from natural language queries."""

RISK_SYSTEM = """You are a financial risk analyst evaluating stock price predictions.

Given prediction metrics, provide a concise risk assessment with:
- risk_rating: "low", "medium", or "high"
- reasoning: 2-3 sentences explaining the rating

Guidelines:
- R² > 0.85 and RMSE < 5% of price → lean low risk
- R² 0.65–0.85 or RMSE 5–15% of price → medium risk
- R² < 0.65 or RMSE > 15% of price → high risk
- days_ahead > 180 adds one risk level
- days_ahead > 365 adds another risk level

Respond with JSON only: {"risk_rating": "...", "reasoning": "..."}"""

REPORT_SYSTEM = """You are a financial report writer. Format stock prediction results as a clean, readable summary.

Include:
- The predicted price with confidence context
- Key model metrics (R², RMSE) explained in plain language
- Risk rating with brief explanation
- A disclaimer that this is a model prediction, not financial advice

Keep the tone professional but accessible. Use clear formatting."""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "analyze_stock",
        "description": (
            "Fetch historical stock data, train a regression model, and predict "
            "the stock price on a future date. Returns prediction and model metrics."
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
                    "description": "Target date for prediction in YYYY-MM-DD format",
                },
                "days": {
                    "type": "integer",
                    "description": "Days of historical data to use (default 365)",
                    "default": 365,
                },
            },
            "required": ["ticker", "target_date"],
        },
    },
    {
        "name": "assess_risk",
        "description": (
            "Evaluate the risk level of a stock prediction based on model metrics "
            "and prediction horizon. Returns a risk rating with reasoning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "predicted_price": {"type": "number"},
                "target_date": {"type": "string"},
                "r2_score": {"type": "number", "description": "R² score from 0 to 1"},
                "rmse": {"type": "number", "description": "Root mean squared error in dollars"},
                "days_ahead": {"type": "integer", "description": "Calendar days until target date"},
                "current_price": {"type": "number", "description": "Most recent closing price"},
            },
            "required": [
                "ticker",
                "predicted_price",
                "target_date",
                "r2_score",
                "rmse",
                "days_ahead",
                "current_price",
            ],
        },
    },
    {
        "name": "generate_report",
        "description": "Format all prediction and risk information into a final readable report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "predicted_price": {"type": "number"},
                "target_date": {"type": "string"},
                "current_price": {"type": "number"},
                "r2_score": {"type": "number"},
                "rmse": {"type": "number"},
                "days_ahead": {"type": "integer"},
                "risk_rating": {"type": "string", "enum": ["low", "medium", "high"]},
                "risk_reasoning": {"type": "string"},
            },
            "required": [
                "ticker",
                "predicted_price",
                "target_date",
                "current_price",
                "r2_score",
                "rmse",
                "days_ahead",
                "risk_rating",
                "risk_reasoning",
            ],
        },
    },
]


def run_analysis_agent(
    ticker: str, target_date: str, days: int = 365
) -> dict[str, Any]:
    """Fetch data, train model, and predict price for a given ticker and date.

    Re-computes an 80/20 chronological eval split to extract test metrics,
    since train_model() refits on the full dataset and does not return metrics.

    Args:
        ticker: Stock ticker symbol.
        target_date: Target date string in YYYY-MM-DD format.
        days: Number of historical trading days to fetch.

    Returns:
        Dictionary with prediction details and model metrics.

    Raises:
        ValueError: If the ticker is invalid or data is insufficient.
    """
    raw_data = fetch_stock_data(ticker, days)
    featured_data = create_features(raw_data)

    # Re-compute eval split to extract test metrics (train_model prints but doesn't return them)
    split_idx = int(len(featured_data) * 0.8)
    train_df = featured_data.iloc[:split_idx]
    test_df = featured_data.iloc[split_idx:]

    eval_model, eval_scaler, _ = train_model(train_df)

    feature_cols = [c for c in featured_data.columns if c != "Close"]
    x_test = eval_scaler.transform(test_df[feature_cols])
    y_test = test_df["Close"].values
    y_pred_test = eval_model.predict(x_test)

    test_r2 = float(r2_score(y_test, y_pred_test))
    test_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_test)))

    # Train final model on full data for prediction
    final_model, final_scaler, training_data = train_model(featured_data)

    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    predicted_price, days_ahead = predict_future_price(
        final_model, final_scaler, training_data, target_dt
    )

    current_price = float(featured_data["Close"].iloc[-1])

    return {
        "ticker": ticker,
        "predicted_price": round(predicted_price, 2),
        "target_date": target_date,
        "current_price": round(current_price, 2),
        "r2_score": round(test_r2, 4),
        "rmse": round(test_rmse, 2),
        "days_ahead": days_ahead,
    }


def run_risk_agent(client: anthropic.Anthropic, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Call the risk assessment LLM sub-agent.

    Args:
        client: Anthropic API client.
        tool_input: Dict containing prediction metrics from analyze_stock.

    Returns:
        Dict with risk_rating and reasoning keys.
    """
    prompt = (
        f"Assess the prediction risk for {tool_input['ticker']}:\n"
        f"- Predicted price: ${tool_input['predicted_price']}\n"
        f"- Current price: ${tool_input['current_price']}\n"
        f"- Target date: {tool_input['target_date']} ({tool_input['days_ahead']} days ahead)\n"
        f"- R² score: {tool_input['r2_score']}\n"
        f"- RMSE: ${tool_input['rmse']}\n"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=[
            {
                "type": "text",
                "text": RISK_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)


def run_report_agent(client: anthropic.Anthropic, tool_input: dict[str, Any]) -> str:
    """Call the report generation LLM sub-agent.

    Args:
        client: Anthropic API client.
        tool_input: Dict containing all prediction and risk data.

    Returns:
        Formatted report string.
    """
    prompt = (
        f"Generate a prediction report for {tool_input['ticker']}:\n"
        f"- Current price: ${tool_input['current_price']}\n"
        f"- Predicted price on {tool_input['target_date']}: ${tool_input['predicted_price']}\n"
        f"- Days ahead: {tool_input['days_ahead']}\n"
        f"- Model R²: {tool_input['r2_score']}\n"
        f"- Model RMSE: ${tool_input['rmse']}\n"
        f"- Risk rating: {tool_input['risk_rating']}\n"
        f"- Risk reasoning: {tool_input['risk_reasoning']}\n"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": REPORT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def execute_tool(
    client: anthropic.Anthropic, tool_name: str, tool_input: dict[str, Any]
) -> str:
    """Dispatch a tool call to the appropriate agent.

    Args:
        client: Anthropic API client.
        tool_name: Name of the tool to execute.
        tool_input: Parameters for the tool.

    Returns:
        JSON-encoded result string.
    """
    if tool_name == "analyze_stock":
        result = run_analysis_agent(
            ticker=tool_input["ticker"],
            target_date=tool_input["target_date"],
            days=tool_input.get("days", 365),
        )
        return json.dumps(result)

    if tool_name == "assess_risk":
        result = run_risk_agent(client, tool_input)
        return json.dumps(result)

    if tool_name == "generate_report":
        report = run_report_agent(client, tool_input)
        return report

    raise ValueError(f"Unknown tool: {tool_name}")


def run_orchestrator(query: str) -> str:
    """Run the orchestrator agent loop for a natural language stock query.

    Executes a manual tool_use loop: sends the query to the orchestrator,
    dispatches tool calls, feeds results back, and returns the final answer.

    Args:
        query: Natural language query (e.g. "What will AAPL be on 2026-08-01?").

    Returns:
        Final text response from the orchestrator.
    """
    client = anthropic.Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]

    system = [
        {
            "type": "text",
            "text": ORCHESTRATOR_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        # Process all tool_use blocks
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            try:
                result_content = execute_tool(client, block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Error: {exc}",
                        "is_error": True,
                    }
                )

        messages.append({"role": "user", "content": tool_results})


async def main() -> None:
    """Parse CLI args and run the stock prediction agent team.

    Args are read from sys.argv. The query may be passed as a single
    positional argument or multiple words joined together.
    """
    parser = argparse.ArgumentParser(
        description="Multi-agent stock price prediction team"
    )
    parser.add_argument(
        "query",
        nargs="+",
        help='Natural language query, e.g. "What will AAPL be on 2026-08-01?"',
    )
    args = parser.parse_args()
    query = " ".join(args.query)

    print(f"Query: {query}\n")
    print("Running agent team...\n")

    result = run_orchestrator(query)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
