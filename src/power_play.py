import pandas as pd
import pandas_ta as ta
import yfinance as yf
import numpy as np

from src import config

def check_power_play(df, sp500_data=None):
    """
    Checks if a stock meets the Power Play setup criteria.
    This involves checking four stages: Trend, Setup, Trigger, and Confirmation.

    Args:
        df (pd.DataFrame): DataFrame with historical stock data (OHLCV).
        ticker_symbol (str): The ticker symbol of the stock.

    Returns:
        tuple: A tuple containing:
            - str: The status ("PASS", "FAIL").
            - str: A reason for the status.
            - dict: A dictionary containing data for charting.
    """
    if df.empty or len(df) < config.PP_TREND_SMA_LONG:
        return "FAIL", "Insufficient data for Power Play analysis.", {}

    # --- Calculate all necessary indicators ---
    _calculate_indicators(df)

    # --- Stage 1: Trend Filter ---
    trend_ok, trend_reason = _check_trend_filter(df, sp500_data)
    if not trend_ok:
        return "FAIL", f"Trend Filter: {trend_reason}", {}

    # --- Stage 2: Setup Detection ---
    setup_ok, setup_reason = _check_setup_detection(df)
    if not setup_ok:
        return "FAIL", f"Setup Detection: {setup_reason}", {}

    # --- Stage 3: Entry Trigger ---
    trigger_ok, trigger_reason = _check_entry_trigger(df)
    if not trigger_ok:
        return "FAIL", f"Entry Trigger: {trigger_reason}", {}

    # --- Stage 4: Confirmation ---
    confirm_ok, confirm_reason = _check_confirmation(df)
    if not confirm_ok:
        return "FAIL", f"Confirmation: {confirm_reason}", {}

    # --- If all stages pass ---
    final_reason = f"{trend_reason}, {setup_reason}, {trigger_reason}, {confirm_reason}"

    chart_data = {
        'sma_short': df[f'SMA_{config.PP_TREND_SMA_SHORT}'],
        'sma_long': df[f'SMA_{config.PP_TREND_SMA_LONG}'],
        'bbands': {
            'lower': df['BBL'],
            'middle': df['BBM'],
            'upper': df['BBU'],
        }
    }

    return "PASS", final_reason, chart_data


def _calculate_indicators(df):
    """Appends all required technical indicators to the DataFrame."""
    # Trend indicators
    df[f'SMA_{config.PP_TREND_SMA_SHORT}'] = ta.sma(df['Close'], length=config.PP_TREND_SMA_SHORT)
    df[f'SMA_{config.PP_TREND_SMA_LONG}'] = ta.sma(df['Close'], length=config.PP_TREND_SMA_LONG)
    df['52W_High'] = df['Close'].rolling(window=252, min_periods=1).max()

    # Setup indicators
    bbands_df = df.ta.bbands(length=config.PP_SETUP_BB_LENGTH, std=config.PP_SETUP_BB_STD)
    if bbands_df is not None and not bbands_df.empty:
        # Assign bands by position to avoid KeyError from name changes (e.g., BBU_20_2.0 vs BBU_20_2)
        df['BBL'] = bbands_df.iloc[:, 0] # Lower band
        df['BBM'] = bbands_df.iloc[:, 1] # Middle band
        df['BBU'] = bbands_df.iloc[:, 2] # Upper band
        df['BBW'] = (df['BBU'] - df['BBL']) / df['BBM']
    else:
        # If BBands calculation fails, fill with NaN to prevent crashes
        df['BBL'] = df['BBM'] = df['BBU'] = df['BBW'] = np.nan

    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=config.PP_SETUP_ATR_LENGTH)
    df['Vol_SMA_Short'] = ta.sma(df['Volume'], length=config.PP_SETUP_VOL_SMA_SHORT)
    df['Vol_SMA_Long'] = ta.sma(df['Volume'], length=config.PP_SETUP_VOL_SMA_LONG)

    # Trigger indicators
    df['Prev_High'] = df['High'].shift(1).rolling(window=config.PP_TRIGGER_HIGH_LOOKBACK).max()
    df['Vol_SMA_Trigger'] = ta.sma(df['Volume'], length=20)


    # Confirmation indicators
    df['RSI'] = ta.rsi(df['Close'], length=config.PP_CONFIRM_RSI_LENGTH)
    df.ta.macd(fast=config.PP_CONFIRM_MACD_FAST, slow=config.PP_CONFIRM_MACD_SLOW, signal=config.PP_CONFIRM_MACD_SIGNAL, append=True)


def _check_trend_filter(df, sp500_data):
    """Checks if the stock meets the strong trend criteria."""
    latest = df.iloc[-1]

    # Condition 1: Long-term trend (Price > 200 SMA, 200 SMA is trending up)
    sma_long = latest[f'SMA_{config.PP_TREND_SMA_LONG}']
    if latest['Close'] < sma_long:
        return False, f"Price {latest['Close']:.2f} is below 200-day SMA {sma_long:.2f}"

    sma_long_trend = df[f'SMA_{config.PP_TREND_SMA_LONG}'].rolling(window=20).mean().diff().iloc[-1]
    if sma_long_trend <= 0:
        return False, "200-day SMA is not trending upwards."

    # Condition 2: Medium-term trend (50 SMA > 200 SMA)
    sma_short = latest[f'SMA_{config.PP_TREND_SMA_SHORT}']
    if sma_short < sma_long:
        return False, f"50-day SMA {sma_short:.2f} is below 200-day SMA {sma_long:.2f}"

    # Condition 3: Momentum (Price is within 25% of 52-week high)
    if latest['Close'] < (latest['52W_High'] * config.PP_TREND_52W_HIGH_THRESHOLD):
        return False, f"Price {latest['Close']:.2f} is >25% off 52-week high {latest['52W_High']:.2f}"

    # Condition 4: Relative Strength (outperforming S&P500)
    if sp500_data is None or sp500_data.empty:
        return True, "Trend is strong (S&P500 data not available)"

    try:
        stock_perf = (df['Close'].iloc[-1] / df['Close'].iloc[-126]) - 1 # Approx 6 months
        sp500_perf = (sp500_data['Close'].iloc[-1] / sp500_data['Close'].iloc[0]) - 1

        if stock_perf < sp500_perf:
            return False, f"Relative strength ({stock_perf:.2%}) is below S&P500 ({sp500_perf:.2%})"
    except Exception as e:
        return False, f"Could not compare Relative Strength to S&P500: {e}"

    return True, "Trend is strong"


def _check_setup_detection(df):
    """Checks for volatility contraction and volume dry-up."""
    latest = df.iloc[-1]

    # Condition 1: Volatility is low
    # Using Bollinger Band Width (BBW) as a measure of volatility
    bbw = latest['BBW']
    bbw_lookback_period = 126 # Approx 6 months
    min_bbw_in_period = df['BBW'].iloc[-bbw_lookback_period:].min()

    # Check if current BBW is near its minimum (e.g., within 10% of the min)
    is_bbw_low = bbw <= (min_bbw_in_period * 1.10)

    # Alternative check: ATR is trending down
    atr_trend = df['ATR'].rolling(window=10).mean().diff().iloc[-1]
    is_atr_decreasing = atr_trend < 0

    if not (is_bbw_low or is_atr_decreasing):
        return False, f"Volatility not contracting (BBW={bbw:.2f}, ATR Trend={atr_trend:.2f})"

    # Condition 2: Volume is drying up
    vol_sma_short = latest['Vol_SMA_Short']
    vol_sma_long = latest['Vol_SMA_Long']
    if vol_sma_short >= vol_sma_long:
        return False, f"Volume not dry (5-day avg {vol_sma_short:,.0f} >= 50-day avg {vol_sma_long:,.0f})"

    return True, "Setup detected (low volatility, volume dry-up)"


def _check_entry_trigger(df):
    """Checks for a price and volume breakout."""
    latest = df.iloc[-1]

    # Condition 1: Price Breakout
    # Check if today's close is higher than the high of the last N days (excluding today)
    if latest['Close'] <= latest['Prev_High']:
        return False, f"No price breakout (Close {latest['Close']:.2f} <= Prev High {latest['Prev_High']:.2f})"

    # Condition 2: Volume Surge
    min_vol = latest['Vol_SMA_Trigger'] * config.PP_TRIGGER_VOL_INCREASE_FACTOR
    if latest['Volume'] < min_vol:
        return False, f"Volume too low ({latest['Volume']:,.0f} < required {min_vol:,.0f})"

    return True, "Entry triggered (Price & Volume breakout)"


def _check_confirmation(df):
    """Checks for confirmation from RSI and MACD."""
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Condition 1: RSI is in the optimal zone (strong but not overbought)
    rsi = latest['RSI']
    if not (config.PP_CONFIRM_RSI_MIN <= rsi < config.PP_CONFIRM_RSI_MAX):
        return False, f"RSI {rsi:.2f} is outside the optimal range ({config.PP_CONFIRM_RSI_MIN}-{config.PP_CONFIRM_RSI_MAX})"

    # Condition 2: MACD histogram is expanding (momentum is accelerating)
    # Using 'MACDh' for the histogram column name from pandas_ta
    if latest[f'MACDh_{config.PP_CONFIRM_MACD_FAST}_{config.PP_CONFIRM_MACD_SLOW}_{config.PP_CONFIRM_MACD_SIGNAL}'] <= prev[f'MACDh_{config.PP_CONFIRM_MACD_FAST}_{config.PP_CONFIRM_MACD_SLOW}_{config.PP_CONFIRM_MACD_SIGNAL}']:
        return False, "MACD histogram is not expanding."

    return True, "Confirmed by RSI and MACD"
