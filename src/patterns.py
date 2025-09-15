import pandas as pd
import datetime as dt
from src import config

def _find_cup_low_and_high(df):
    """Finds the absolute low of the cup and the subsequent high point (left lip)."""
    if df.empty:
        return None, None, "History is empty"

    cup_bottom_price = df['Low'].min()
    cup_bottom_date = df['Low'].idxmin()

    # The high must come after the bottom and at least 30 days before today
    look_for_high_after_bottom_df = df.loc[cup_bottom_date : dt.date.today() - dt.timedelta(days=30)]
    if look_for_high_after_bottom_df.empty:
        return None, None, "Not enough data after cup bottom to find a high"

    cup_high_price = look_for_high_after_bottom_df['High'].max()
    cup_high_date = look_for_high_after_bottom_df['High'].idxmax()

    # Basic check for cup depth
    if not cup_high_price > cup_bottom_price * config.CUP_MIN_DEPTH_FACTOR:
        return None, None, f"Cup is not deep enough (< {config.CUP_MIN_DEPTH_FACTOR}x)"

    return cup_bottom_date, cup_high_date, None

def _check_base_formation(df, cup_high_date, cup_high_price):
    """Checks for a valid consolidation base after the cup's left lip."""
    base_df = df.loc[cup_high_date:]

    # Check for price range during base formation
    base_top_price = cup_high_price * config.BASE_DEPTH_MAX_FACTOR
    base_bottom_price = cup_high_price * config.BASE_DEPTH_MIN_FACTOR

    potential_base_df = base_df.query('@base_bottom_price <= Close <= @base_top_price')
    if potential_base_df.empty:
        return None, "No valid base consolidation period found"

    base_start_date = potential_base_df.index[0]
    base_end_date = potential_base_df.index[-1]

    # Check base duration
    base_duration = (base_end_date - cup_high_date).days
    if not (config.BASE_MIN_DURATION_DAYS <= base_duration <= config.BASE_MAX_DURATION_DAYS):
        return None, f"Base duration ({base_duration} days) is out of range"

    # Check volatility during the base
    actual_base_df = df.loc[base_start_date:base_end_date]
    volatility = actual_base_df.Close.std() / actual_base_df.Close.mean()
    if volatility > config.BASE_MAX_VOLATILITY:
        return None, f"Base volatility ({volatility:.2f}) is too high"

    return base_start_date, None


def _check_handle_formation(df, base_start_date, cup_high_price):
    """Checks for the handle formation after the base."""
    # Find the right lip of the cup (approach to the old high)
    cup_lip_top = cup_high_price * config.CUP_LIP_MAX_FACTOR
    cup_lip_bottom = cup_high_price * config.CUP_LIP_MIN_FACTOR

    right_lip_df = df.query('index >= @base_start_date and @cup_lip_bottom <= High <= @cup_lip_top')
    if right_lip_df.empty:
        return None, None, "Price did not form a right cup lip"

    handle_start_date = right_lip_df.index[0]

    # Look for the handle pullback in the weeks following the right lip
    handle_lookahead_end_date = handle_start_date + dt.timedelta(days=config.HANDLE_MAX_DURATION_DAYS)
    handle_df = df.loc[handle_start_date:handle_lookahead_end_date]
    if handle_df.empty:
        return None, None, "Not enough data to form a handle"

    handle_peak_price = handle_df['High'].max()

    # Check for a slight pullback for the handle
    handle_pullback_top = handle_peak_price * config.HANDLE_DEPTH_MAX_FACTOR
    handle_pullback_bottom = handle_peak_price * config.HANDLE_DEPTH_MIN_FACTOR

    # The handle must form within a few days of its peak and be above the 50MA
    handle_pullback_start_date = handle_df['High'].idxmax() + dt.timedelta(days=config.HANDLE_MIN_DURATION_DAYS)

    pullback_df = df.query(
        'index >= @handle_pullback_start_date and '
        '@handle_pullback_bottom <= Low <= @handle_pullback_top and '
        'MA50 <= Close'
    )

    if pullback_df.empty:
        # If no classic pullback, the pivot point is the handle's peak
        pivot_price = handle_peak_price
        handle_low_date = handle_df['High'].idxmax()
        if pivot_price > cup_lip_top:
             return None, None, "Handle peak is too high (breakout without a handle)"
    else:
        # If there is a pullback, the pivot is still the handle's peak
        pivot_price = handle_peak_price
        handle_low_date = pullback_df['Low'].idxmin()

    return handle_low_date, pivot_price, None

def _check_pivot_breakout(df, handle_low_date, pivot_price):
    """Checks for a breakout above the pivot point with high volume."""
    breakout_lookahead_end_date = handle_low_date + dt.timedelta(days=config.PIVOT_LOOKAHEAD_DAYS)

    pivot_df = df.query('@handle_low_date < index <= @breakout_lookahead_end_date and High >= @pivot_price')

    if pivot_df.empty:
        return False, "No pivot breakout within the lookahead period"

    # Check for volume breakout on the first day it crosses the pivot
    breakout_day = pivot_df.iloc[0]
    mean_volume_50d = df['Volume'].rolling(window=50).mean().loc[breakout_day.name]

    if breakout_day['Volume'] > mean_volume_50d * config.VOLUME_BREAKOUT_FACTOR:
        return True, f"Pattern detected with volume breakout on {pivot_df.index[0].date()}"

    return False, "Pivot breakout occurred but without sufficient volume"

def check_cup_with_handle(df_hist):
    """
    Checks for a Cup With Handle (CWH) chart pattern.
    This function is a refactored, more readable version of the original logic.

    Returns:
        A tuple containing:
        - status (str): "FAIL", "WATCH", or "BREAKOUT"
        - reason (str): A description of the result.
    """
    # Ensure data is sorted and has the required MA50
    df = df_hist.sort_index()
    if 'MA50' not in df:
        df['MA50'] = df['Close'].rolling(window=50).mean()

    # Stage 1: Find the major low and subsequent high that form the cup.
    cup_bottom_date, cup_high_date, err = _find_cup_low_and_high(df)
    if err:
        return "FAIL", f"Stage 1 (Cup Shape): {err}"

    cup_high_price = df.loc[cup_high_date, 'High']

    # Stage 2: Verify the consolidation base.
    base_start_date, err = _check_base_formation(df, cup_high_date, cup_high_price)
    if err:
        return "FAIL", f"Stage 2 (Base): {err}"

    # Stage 3: Check for the handle formation.
    handle_low_date, pivot_price, err = _check_handle_formation(df, base_start_date, cup_high_price)
    if err:
        return "FAIL", f"Stage 3 (Handle): {err}"

    # Stage 4: Look for a pivot breakout.
    is_breakout, reason = _check_pivot_breakout(df, handle_low_date, pivot_price)
    if not is_breakout:
        # Passed stages 1-3, but hasn't broken out yet. This is a "watch" case.
        return "WATCH", f"Awaiting Breakout: {reason}"

    # Passed all stages, including breakout.
    return "BREAKOUT", reason
