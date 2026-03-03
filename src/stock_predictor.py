#!/usr/bin/env python3
"""
Stock Price Predictor
Downloads historical stock data and predicts future prices using regression.
Features interactive Plotly charts with hover-to-view price details.
Compare up to 3 stocks, including S&P 500 index for market comparison.

Usage: python src/stock_predictor.py <TICKER> [TICKER2] <YYYY-MM-DD> [--days DAYS] [--plot] [--sp500]
       python src/stock_predictor.py NVDA 2026-03-15 --days 365 --plot
       python src/stock_predictor.py NVDA AAPL 2026-04-01 --days 730 --plot
       python src/stock_predictor.py NVDA 2026-03-15 --sp500 --plot
       python src/stock_predictor.py --demo
"""

import sys
import argparse
import traceback
from datetime import datetime, timedelta

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score
    import plotly.graph_objects as go
except ImportError as e:
    print("ERROR: Missing required packages!")
    print("\nPlease install required packages with:")
    print("  pip install yfinance scikit-learn pandas numpy plotly")
    print(f"\nMissing module: {e}")
    sys.exit(1)

MIN_DAYS = 60
MAX_DAYS = 25 * 365  # ~25 years


def fetch_stock_data(ticker: str, days: int) -> pd.DataFrame:
    """Download and validate stock data in a single API call.

    Raises ValueError with a descriptive message if the ticker is invalid,
    the requested period is out of range, or insufficient data is available.
    """
    if days < MIN_DAYS:
        raise ValueError(
            f"days ({days}) is too small; minimum is {MIN_DAYS} days for meaningful predictions."
        )
    if days > MAX_DAYS:
        raise ValueError(
            f"days ({days}) is too large; maximum is {MAX_DAYS} days (~25 years)."
        )

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days + 30)  # extra buffer for weekends/holidays

    print(f"Downloading {ticker} data ({days} days)...")
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)

    if df.empty:
        raise ValueError(
            f"No data for '{ticker}'. Check the ticker symbol and your internet connection."
        )

    # Trim to the requested window
    df = df.tail(days)
    actual_days = len(df)

    if actual_days < days * 0.7:
        raise ValueError(
            f"'{ticker}' only has {actual_days} trading days available; "
            f"{days} were requested. Use a smaller --days value."
        )

    print(f"✓ Downloaded {actual_days} trading days for {ticker}")
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create features for the regression model."""
    data = df.copy()
    data['DayNumber'] = range(len(data))
    data['MA_7'] = data['Close'].rolling(window=7).mean()
    data['MA_30'] = data['Close'].rolling(window=30).mean()
    data['Volume_MA'] = data['Volume'].rolling(window=7).mean()
    data['Price_Change'] = data['Close'].pct_change()
    data['Volatility'] = data['Close'].rolling(window=7).std()
    data = data.dropna()
    return data


def train_model(
    data: pd.DataFrame,
) -> tuple[LinearRegression, StandardScaler, pd.DataFrame]:
    """Train a regression model and report honest out-of-sample performance.

    Uses an 80/20 chronological split for evaluation, then refits on all data
    so predictions use the full history.
    """
    feature_cols = ['DayNumber', 'MA_7', 'MA_30', 'Volume_MA', 'Volatility']
    X = data[feature_cols].values
    y = data['Close'].values

    # Chronological 80/20 split — no shuffling for time-series data
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    eval_scaler = StandardScaler()
    X_train_scaled = eval_scaler.fit_transform(X_train)
    X_test_scaled = eval_scaler.transform(X_test)

    eval_model = LinearRegression()
    eval_model.fit(X_train_scaled, y_train)

    y_pred_train = eval_model.predict(X_train_scaled)
    y_pred_test = eval_model.predict(X_test_scaled)

    train_r2 = r2_score(y_train, y_pred_train)
    train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
    train_mae = np.mean(np.abs(y_train - y_pred_train))

    test_r2 = r2_score(y_test, y_pred_test)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    test_mae = np.mean(np.abs(y_test - y_pred_test))

    print("\nModel Performance (80/20 chronological split):")
    print(f"  Train — R²: {train_r2:.4f}, RMSE: ${train_rmse:.2f}, MAE: ${train_mae:.2f}")
    print(f"  Test  — R²: {test_r2:.4f}, RMSE: ${test_rmse:.2f}, MAE: ${test_mae:.2f}")
    if test_r2 < 0.5:
        print("  ⚠️  Low out-of-sample R² — treat this prediction with extra caution.")

    # Refit on the full dataset for final predictions
    final_scaler = StandardScaler()
    X_all_scaled = final_scaler.fit_transform(X)
    final_model = LinearRegression()
    final_model.fit(X_all_scaled, y)

    return final_model, final_scaler, data


def predict_future_price(
    model: LinearRegression,
    scaler: StandardScaler,
    training_data: pd.DataFrame,
    target_date: datetime,
) -> tuple[float, int]:
    """Predict stock price for a future date.

    Note: technical indicator features are held at their last known values.
    This is a simplification — real forecasts would require simulating those
    values forward, which is itself uncertain.
    """
    last_date = training_data.index[-1]

    # Normalise timezone info so subtraction works
    last_date_naive = (
        last_date.tz_localize(None)
        if hasattr(last_date, 'tz_localize') and last_date.tzinfo is not None
        else last_date.replace(tzinfo=None) if last_date.tzinfo is not None else last_date
    )
    target_date_naive = (
        target_date.replace(tzinfo=None) if target_date.tzinfo is not None else target_date
    )

    days_ahead = (target_date_naive - last_date_naive).days
    if days_ahead <= 0:
        raise ValueError(f"Target date must be after {last_date_naive.date()}")

    last_row = training_data.iloc[-1]
    day_number = last_row['DayNumber'] + days_ahead

    features = np.array([[
        day_number,
        last_row['MA_7'],
        last_row['MA_30'],
        last_row['Volume_MA'],
        last_row['Volatility'],
    ]])
    features_scaled = scaler.transform(features)
    predicted_price = model.predict(features_scaled)[0]

    return predicted_price, days_ahead


def visualize_prediction(
    training_data: pd.DataFrame,
    target_date: datetime,
    predicted_price: float,
    ticker: str,
) -> None:
    """Print an ASCII chart of the last 30 days plus the prediction."""
    print(f"\n{ticker} — Price Trend (Last 30 Days + Prediction):")
    print("-" * 70)

    recent_data = training_data.tail(30)
    prices = list(recent_data['Close'].values) + [predicted_price]
    dates = [d.strftime('%m/%d') for d in recent_data.index] + [target_date.strftime('%m/%d')]

    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price

    step = max(1, len(prices) // 10)
    for i in range(0, len(prices), step):
        normalized = (prices[i] - min_price) / price_range if price_range > 0 else 0.5
        bar = '█' * int(normalized * 50)
        marker = '→' if i == len(prices) - 1 else ' '
        print(f"{dates[i]}: ${prices[i]:7.2f} {marker} {bar}")

    print("-" * 70)


def plot_stock_price(
    stock_data_list: list[dict],
    target_date: datetime,
) -> bool:
    """Create an interactive Plotly chart of historical prices and predictions.

    Args:
        stock_data_list: List of dicts with keys: 'ticker', 'training_data', 'predicted_price'.
        target_date: Target date for predictions.

    Returns:
        True if the chart was displayed, False on error.
    """
    try:
        colors = ['#2E86AB', '#E63946', '#06A77D']
        ma_colors = [['#A23B72', '#F18F01'], ['#FF006E', '#FB5607'], ['#4CC9F0', '#F72585']]
        pred_colors = ['#C73E1D', '#8338EC', '#06D6A0']

        fig = go.Figure()

        for idx, stock_data in enumerate(stock_data_list):
            ticker = stock_data['ticker']
            training_data = stock_data['training_data']
            predicted_price = stock_data['predicted_price']

            dates = training_data.index
            prices = training_data['Close'].values

            fig.add_trace(go.Scatter(
                x=dates,
                y=prices,
                mode='lines',
                name=f'{ticker} Historical',
                line=dict(color=colors[idx], width=2.5),
                hovertemplate=(
                    '<b>%{fullData.name}</b><br>'
                    'Date: %{x|%Y-%m-%d}<br>'
                    'Price: $%{y:.2f}<br>'
                    '<extra></extra>'
                ),
            ))

            fig.add_trace(go.Scatter(
                x=dates,
                y=training_data['MA_7'].values,
                mode='lines',
                name=f'{ticker} 7-Day MA',
                line=dict(color=ma_colors[idx][0], width=1.5, dash='dash'),
                opacity=0.6,
                hovertemplate=(
                    '<b>%{fullData.name}</b><br>'
                    'Date: %{x|%Y-%m-%d}<br>'
                    'MA-7: $%{y:.2f}<br>'
                    '<extra></extra>'
                ),
            ))

            fig.add_trace(go.Scatter(
                x=dates,
                y=training_data['MA_30'].values,
                mode='lines',
                name=f'{ticker} 30-Day MA',
                line=dict(color=ma_colors[idx][1], width=1.5, dash='dash'),
                opacity=0.6,
                hovertemplate=(
                    '<b>%{fullData.name}</b><br>'
                    'Date: %{x|%Y-%m-%d}<br>'
                    'MA-30: $%{y:.2f}<br>'
                    '<extra></extra>'
                ),
            ))

            last_date = training_data.index[-1]
            last_price = training_data['Close'].iloc[-1]
            price_change = predicted_price - last_price
            pct_change = (price_change / last_price) * 100

            fig.add_trace(go.Scatter(
                x=[last_date, target_date],
                y=[last_price, predicted_price],
                mode='lines',
                name=f'{ticker} Projection',
                line=dict(color=pred_colors[idx], width=2, dash='dot'),
                opacity=0.7,
                hovertemplate=(
                    '<b>%{fullData.name}</b><br>'
                    'Date: %{x|%Y-%m-%d}<br>'
                    'Price: $%{y:.2f}<br>'
                    '<extra></extra>'
                ),
            ))

            fig.add_trace(go.Scatter(
                x=[target_date],
                y=[predicted_price],
                mode='markers',
                name=f'{ticker} Prediction',
                marker=dict(
                    color=pred_colors[idx],
                    size=15,
                    symbol='star',
                    line=dict(color='white', width=1),
                ),
                hovertemplate=(
                    '<b>%{fullData.name}</b><br>'
                    f'Target Date: {target_date.strftime("%Y-%m-%d")}<br>'
                    f'Predicted Price: ${predicted_price:.2f}<br>'
                    f'Change: ${price_change:+.2f} ({pct_change:+.2f}%)<br>'
                    '<extra></extra>'
                ),
            ))

        tickers_str = ' vs '.join([s['ticker'] for s in stock_data_list])

        annotation_lines = [f"Target: {target_date.strftime('%Y-%m-%d')}"]
        for stock_data in stock_data_list:
            last_price = stock_data['training_data']['Close'].iloc[-1]
            pred = stock_data['predicted_price']
            change = pred - last_price
            pct = (change / last_price) * 100
            annotation_lines.append(
                f"<b>{stock_data['ticker']}</b>: ${last_price:.2f} → ${pred:.2f} "
                f"({change:+.2f}, {pct:+.2f}%)"
            )

        fig.update_layout(
            title=dict(
                text=f'{tickers_str} Stock Price Comparison and Predictions',
                font=dict(size=18, color='#1f2937'),
                x=0.5,
                xanchor='center',
            ),
            xaxis=dict(
                title='Date',
                titlefont=dict(size=14, color='#374151'),
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=False,
            ),
            yaxis=dict(
                title='Stock Price ($)',
                titlefont=dict(size=14, color='#374151'),
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=False,
            ),
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white',
            legend=dict(
                orientation='v',
                yanchor='top',
                y=0.99,
                xanchor='left',
                x=0.01,
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='rgba(0,0,0,0.2)',
                borderwidth=1,
            ),
            margin=dict(l=60, r=40, t=100, b=60),
            height=700,
            annotations=[dict(
                text='<br>'.join(annotation_lines),
                xref='paper',
                yref='paper',
                x=0.99,
                y=0.99,
                xanchor='right',
                yanchor='top',
                bgcolor='rgba(255, 248, 220, 0.9)',
                bordercolor='rgba(0,0,0,0.3)',
                borderwidth=1,
                borderpad=8,
                font=dict(size=11, family='monospace'),
                align='left',
                showarrow=False,
            )],
        )

        fig.update_xaxes(rangeslider_visible=True)

        print("\n📊 Displaying interactive stock price chart...")
        print("💡 Hover over the chart to see detailed price information at any point!")
        print("💡 Use the range slider at the bottom to zoom in/out")
        print("💡 Click legend items to show/hide specific data series")
        fig.show()
        return True

    except Exception as e:
        print(f"\n⚠️  Warning: Could not create plot: {e}")
        print("Continuing without graphical visualization...")
        return False


def main() -> None:
    """Entry point — parse arguments, run prediction pipeline."""
    parser = argparse.ArgumentParser(
        description='Predict stock price using regression analysis. Compare up to 3 stocks.',
        epilog=(
            'Examples:\n'
            '  python src/stock_predictor.py NVDA 2026-03-15\n'
            '  python src/stock_predictor.py NVDA AAPL 2026-04-01 --days 730 --plot\n'
            '  python src/stock_predictor.py NVDA 2026-03-15 --sp500 --plot\n'
            '  python src/stock_predictor.py TSLA MSFT 2026-05-15 --days 500 --plot\n'
            '  python src/stock_predictor.py MSFT 2026-06-01 --plot --visualize\n'
            '  python src/stock_predictor.py --demo --sp500 --plot'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'inputs',
        type=str,
        nargs='*',
        help='Stock ticker(s) and target date. Format: TICKER [TICKER2] [TICKER3] YYYY-MM-DD',
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help=f'Historical days for training (default: 365, min: {MIN_DAYS}, max: {MAX_DAYS})',
    )
    parser.add_argument('--demo', action='store_true', help='Run demo: NVDA 30 days ahead')
    parser.add_argument('--visualize', action='store_true', help='Show ASCII chart')
    parser.add_argument(
        '--plot', action='store_true', help='Show interactive Plotly chart'
    )
    parser.add_argument('--sp500', action='store_true', help='Include S&P 500 (^GSPC)')
    parser.add_argument('--debug', action='store_true', help='Print full tracebacks on errors')

    args = parser.parse_args()

    if args.demo:
        tickers = ['NVDA']
        target_date = datetime.now() + timedelta(days=30)
        days_prior = 365
        print("🎯 DEMO MODE: Predicting NVDA 30 days into the future")
        print(f"Ticker: {tickers[0]}")
        print(f"Target date: {target_date.strftime('%Y-%m-%d')}")
        print(f"Using {days_prior} days of historical data\n")
    else:
        if not args.inputs or len(args.inputs) < 2:
            parser.print_help()
            print("\n❌ ERROR: Need at least TICKER and TARGET_DATE (or use --demo)")
            print("\nExamples:")
            print("  python src/stock_predictor.py NVDA 2026-03-15")
            print("  python src/stock_predictor.py NVDA AAPL 2026-04-01 --days 730 --plot")
            print("  python src/stock_predictor.py --demo")
            sys.exit(1)

        potential_tickers = args.inputs[:-1]
        date_str = args.inputs[-1]

        if len(potential_tickers) == 0 or len(potential_tickers) > 3:
            print("❌ ERROR: Please provide 1-3 stock tickers")
            print(f"You provided: {len(potential_tickers)} ticker(s)")
            sys.exit(1)

        tickers = [t.upper() for t in potential_tickers]
        days_prior = args.days

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print("❌ ERROR: Date must be in YYYY-MM-DD format")
            print(f"You provided: {date_str}")
            sys.exit(1)

        if target_date <= datetime.now():
            print("❌ ERROR: Target date must be in the future")
            print(f"Target date: {target_date.date()}")
            print(f"Current date: {datetime.now().date()}")
            sys.exit(1)

    if args.sp500 and '^GSPC' not in tickers:
        tickers.append('^GSPC')
        print("📊 Adding S&P 500 (^GSPC) for comparison\n")

    if len(tickers) > 3:
        print("❌ ERROR: Maximum 3 stocks can be compared at once")
        print(f"You requested: {', '.join(tickers)}")
        print("Please reduce the number of tickers or remove --sp500 flag")
        sys.exit(1)

    print("=" * 70)
    print("STOCK PRICE PREDICTION")
    print("=" * 70)
    print(f"Ticker Symbol(s): {', '.join(tickers)}")
    print(f"Target Date: {target_date.strftime('%Y-%m-%d')}")
    print(f"Historical Data Period: {days_prior} days")
    print("=" * 70)
    print()

    stock_results = []

    for ticker_idx, ticker in enumerate(tickers):
        if len(tickers) > 1:
            print(f"\n{'=' * 70}")
            print(f"PROCESSING {ticker} ({ticker_idx + 1}/{len(tickers)})")
            print(f"{'=' * 70}\n")

        try:
            print(f"Step 1: Fetching {ticker} data...")
            df = fetch_stock_data(ticker=ticker, days=days_prior)
            print()

            print(f"Recent {ticker} closing prices:")
            print(df['Close'].tail())
            print(f"\nLatest close: ${df['Close'].iloc[-1]:.2f} on {df.index[-1].date()}")
            print()

            print(f"Step 2: Creating features for {ticker}...")
            data = create_features(df)
            print(f"✓ Created features with {len(data)} data points\n")

            print(f"Step 3: Training regression model for {ticker}...")
            model, scaler, training_data = train_model(data)
            print()

            print(f"Step 4: Predicting price for {ticker}...")
            predicted_price, days_ahead = predict_future_price(
                model, scaler, training_data, target_date
            )
            print("✓ Prediction complete\n")

            stock_results.append({
                'ticker': ticker,
                'training_data': training_data,
                'predicted_price': predicted_price,
                'days_ahead': days_ahead,
            })

        except Exception as e:
            print(f"\n❌ ERROR processing {ticker}: {e}")
            if args.debug:
                traceback.print_exc()
            if len(tickers) > 1:
                print(f"Skipping {ticker} and continuing with remaining tickers...")
                continue
            sys.exit(1)

    if not stock_results:
        print("\n❌ ERROR: No stocks were successfully processed.")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print("PREDICTION RESULTS")
    print(f"{'=' * 70}")

    for result in stock_results:
        ticker = result['ticker']
        training_data = result['training_data']
        predicted_price = result['predicted_price']
        days_ahead = result['days_ahead']

        last_price = training_data['Close'].iloc[-1]
        price_change = predicted_price - last_price
        pct_change = (price_change / last_price) * 100

        print(f"\n{ticker}:")
        print(f"  Last known price ({training_data.index[-1].date()}): ${last_price:.2f}")
        print(f"  Predicted price for {target_date.date()}: ${predicted_price:.2f}")
        print(f"  Days ahead: {days_ahead}")
        print(f"  Expected change: ${price_change:+.2f} ({pct_change:+.2f}%)")

    print(f"{'=' * 70}")

    if args.visualize or args.demo:
        for result in stock_results:
            visualize_prediction(
                result['training_data'],
                target_date,
                result['predicted_price'],
                result['ticker'],
            )

    if args.plot and stock_results:
        plot_stock_price(stock_results, target_date)

    print("\n⚠️  DISCLAIMER: This is a simple linear model for educational purposes only.")
    print("Predictions extrapolate a trend line and freeze technical indicators at their")
    print("last known values — real market movements are far more complex.")
    print("Do NOT use this for actual investment decisions.")


if __name__ == '__main__':
    main()
