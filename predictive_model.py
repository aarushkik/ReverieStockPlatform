import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("stock_agent.predictive_model")

# Attempt imports for ML packages
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, precision_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Predictive ML model running in fallback mode.")


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def extract_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts quantitative technical and momentum features from historical price DataFrame.
    Expected columns: 'Close', 'Open', 'High', 'Low', 'Volume'
    """
    if df.empty or len(df) < 30 or 'Close' not in df.columns:
        return pd.DataFrame()

    data = df.copy().sort_index()
    close = data['Close']
    
    # 1. Price Lags & Historical Return Horizons
    data['ret_1d'] = close.pct_change(1)
    data['ret_3d'] = close.pct_change(3)
    data['ret_5d'] = close.pct_change(5)
    data['ret_10d'] = close.pct_change(10)
    data['ret_20d'] = close.pct_change(20)

    # 2. Moving Average Distance Ratios
    sma5 = close.rolling(5).mean()
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    data['dist_sma5'] = (close - sma5) / sma5
    data['dist_sma20'] = (close - sma20) / sma20
    data['dist_sma50'] = (close - sma50) / sma50
    data['dist_sma200'] = (close - sma200) / sma200
    data['sma5_sma20_ratio'] = (sma5 - sma20) / sma20

    # 3. Volatility Metrics
    data['volatility_10d'] = data['ret_1d'].rolling(10).std()
    data['volatility_20d'] = data['ret_1d'].rolling(20).std()

    # 4. Technical Oscillators: RSI, MACD, Bollinger %B
    data['rsi_14'] = calculate_rsi(close, 14)
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_sig = macd_line.ewm(span=9, adjust=False).mean()
    data['macd_diff'] = macd_line - macd_sig

    std20 = close.rolling(20).std()
    upper_bb = sma20 + (std20 * 2)
    lower_bb = sma20 - (std20 * 2)
    bb_range = upper_bb - lower_bb
    data['bb_pct_b'] = np.where(bb_range > 0, (close - lower_bb) / bb_range, 0.5)

    # 5. High-Low Spread & Volume Dynamics
    if 'High' in data.columns and 'Low' in data.columns:
        data['hl_spread_pct'] = (data['High'] - data['Low']) / close
    else:
        data['hl_spread_pct'] = 0.0

    if 'Volume' in data.columns and data['Volume'].sum() > 0:
        vol_sma20 = data['Volume'].rolling(20).mean()
        data['vol_ratio'] = np.where(vol_sma20 > 0, data['Volume'] / vol_sma20, 1.0)
    else:
        data['vol_ratio'] = 1.0

    # 6. Targets (5-day forward return direction & value)
    data['target_ret_5d'] = close.shift(-5) / close - 1.0
    data['target_dir_5d'] = (data['target_ret_5d'] > 0.005).astype(int)

    return data


FEATURE_COLUMNS = [
    'ret_1d', 'ret_3d', 'ret_5d', 'ret_10d', 'ret_20d',
    'dist_sma5', 'dist_sma20', 'dist_sma50', 'sma5_sma20_ratio',
    'volatility_10d', 'volatility_20d', 'rsi_14', 'macd_diff',
    'bb_pct_b', 'hl_spread_pct', 'vol_ratio'
]


def train_predictive_model(symbol: str, df: pd.DataFrame) -> dict:
    """
    Trains a Quantitative Machine Learning predictive model on historical OHLCV data.
    Returns prediction metrics, probability scores, feature importances, and 30-day forward forecast.
    """
    feature_df = extract_ml_features(df)
    if feature_df.empty or len(feature_df.dropna(subset=FEATURE_COLUMNS)) < 50:
        return build_fallback_prediction(symbol, df, 'insufficient feature rows')

    clean_df = feature_df.dropna(subset=FEATURE_COLUMNS + ['target_dir_5d'])
    if len(clean_df) < 40:
        return build_fallback_prediction(symbol, df, 'fewer than 40 labelled samples')

    X = clean_df[FEATURE_COLUMNS]
    y = clean_df['target_dir_5d']

    # Train / Test split (80% historical train, 20% recent backtest)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    if SKLEARN_AVAILABLE and len(X_train) >= 30:
        try:
            # Model Ensemble: Random Forest + Gradient Boosting
            rf_model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            rf_model.fit(X_train, y_train)

            gb_model = GradientBoostingClassifier(n_estimators=60, max_depth=3, random_state=42)
            gb_model.fit(X_train, y_train)

            # Evaluate backtest performance
            y_pred_rf = rf_model.predict(X_test)
            y_pred_gb = gb_model.predict(X_test)

            accuracy_rf = accuracy_score(y_test, y_pred_rf)
            accuracy_gb = accuracy_score(y_test, y_pred_gb)
            combined_acc = float((accuracy_rf + accuracy_gb) / 2.0)

            # Feature importances
            importances = (rf_model.feature_importances_ + gb_model.feature_importances_) / 2.0
            feat_imp = sorted(
                [{"feature": f, "importance": float(round(imp * 100, 2))} for f, imp in zip(FEATURE_COLUMNS, importances)],
                key=lambda x: x["importance"],
                reverse=True
            )

            # Current features (latest bar)
            latest_features = feature_df[FEATURE_COLUMNS].tail(1).fillna(0.0)
            prob_rf = rf_model.predict_proba(latest_features)[0][1]
            prob_gb = gb_model.predict_proba(latest_features)[0][1]
            bullish_prob = float((prob_rf + prob_gb) / 2.0)

            # Determine prediction tag
            if bullish_prob > 0.58:
                prediction_label = "Bullish"
            elif bullish_prob < 0.42:
                prediction_label = "Bearish"
            else:
                prediction_label = "Neutral"

            confidence_score = int(round(50 + abs(bullish_prob - 0.5) * 80))
            confidence_score = max(52, min(95, confidence_score))
            hit_rate_pct = float(round(combined_acc * 100, 1))

            # 30-Day Forward Forecast Path
            forecast_df = generate_forward_forecast(df, bullish_prob, days_ahead=30)

            return {
                "success": True,
                "symbol": symbol,
                "prediction": prediction_label,
                "bullish_probability": float(round(bullish_prob * 100, 1)),
                "confidence_pct": confidence_score,
                "backtest_accuracy_pct": hit_rate_pct,
                "samples_trained": len(X_train),
                "samples_tested": len(X_test),
                "feature_importances": feat_imp[:8],
                "forecast": forecast_df.to_dict(orient="records"),
                "is_ml_trained": True
            }
        except Exception as e:
            logger.warning(f"Failed ML model training for {symbol}: {e}")
            return build_fallback_prediction(symbol, df, f'training failed: {e}')
    else:
        return build_fallback_prediction(symbol, df, 'scikit-learn unavailable')


def generate_forward_forecast(df: pd.DataFrame, bullish_prob: float, days_ahead: int = 30) -> pd.DataFrame:
    """
    Generates a 30-day forward price trajectory with upper and lower 95% confidence bounds.
    """
    if df.empty or 'Close' not in df.columns:
        return pd.DataFrame()

    last_close = float(df['Close'].dropna().iloc[-1])
    returns = df['Close'].pct_change().dropna()
    daily_vol = float(returns.tail(30).std()) if len(returns) >= 30 else 0.018

    # Daily drift estimate calculated from ML probability output
    # Neutral prob = 0.50 -> 0 drift
    daily_drift = (bullish_prob - 0.50) * 0.003

    last_date = df.index[-1]
    if not isinstance(last_date, datetime):
        try:
            last_date = pd.to_datetime(last_date)
        except Exception:
            last_date = datetime.now()

    future_records = []
    current_price = last_close
    current_date = last_date

    for day in range(1, days_ahead + 1):
        current_date += timedelta(days=1)
        # Skip weekends
        while current_date.weekday() >= 5:
            current_date += timedelta(days=1)

        current_price *= (1.0 + daily_drift)
        cum_std = daily_vol * np.sqrt(day)
        upper_bound = current_price * (1.0 + 1.96 * cum_std)
        lower_bound = current_price * max(0.1, (1.0 - 1.96 * cum_std))

        future_records.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "predicted_close": float(round(current_price, 2)),
            "upper_bound": float(round(upper_bound, 2)),
            "lower_bound": float(round(lower_bound, 2))
        })

    return pd.DataFrame(future_records)


def build_fallback_prediction(symbol: str, df: pd.DataFrame, reason: str = "") -> dict:
    """Returned when the model could not be trained. Reports that, and nothing else.

    This previously returned success=True alongside a full set of invented
    metrics: a bullish probability of 52.0%, a confidence of 60%, a
    *backtest accuracy of 58.5%* that was never computed, and five hardcoded
    feature importances (rsi_14 22.4, dist_sma20 18.2, ...) presented exactly
    like measured ones. A user reading the model card saw an evaluated model
    where none had been trained; only an is_ml_trained flag distinguished them.

    A prediction that could not be made is not a neutral prediction.
    """
    return {
        "success": False,
        "symbol": symbol,
        "reason": reason or (
            "not enough clean history to train "
            f"(need ~50 usable rows, have {len(df) if df is not None else 0})"
        ),
        "prediction": None,
        "bullish_probability": None,
        "confidence_pct": None,
        "backtest_accuracy_pct": None,
        "samples_trained": 0,
        "samples_tested": 0,
        "feature_importances": [],
        "forecast": [],
        "is_ml_trained": False,
    }
