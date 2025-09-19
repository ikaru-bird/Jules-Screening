import pandas as pd
import datetime as dt
from src import config

def _check_prior_uptrend(df, left_lip_date):
    """
    Checks if there was a significant uptrend prior to the cup's formation.
    The price should have risen by at least UPTREND_MIN_RISE_FACTOR in the UPTREND_LOOKBACK_DAYS.
    """
    uptrend_start_date = left_lip_date - dt.timedelta(days=config.UPTREND_LOOKBACK_DAYS)
    uptrend_df = df.loc[uptrend_start_date:left_lip_date]

    if uptrend_df.empty:
        return False, "Not enough data for uptrend check"

    start_price = uptrend_df['Close'].iloc[0]
    end_price = df.loc[left_lip_date, 'High']

    if end_price >= start_price * config.UPTREND_MIN_RISE_FACTOR:
        return True, "Prior uptrend confirmed"
    else:
        return False, f"Price did not rise enough in the {config.UPTREND_LOOKBACK_DAYS} days prior to the cup"

def _find_cup_shape(df):
    """
    Identifies a valid cup shape based on a high on the left, a bottom, and a high on the right.
    This is a more robust method than finding the absolute low first.
    """
    if len(df) < config.CUP_MIN_DURATION_DAYS:
        return None, None, None, "Not enough historical data to form a cup"

    # Find the high point (left lip) in the first 75% of the lookback period
    left_side_df = df.iloc[:int(len(df) * 0.75)]
    left_lip_date = left_side_df['High'].idxmax()
    left_lip_price = left_side_df['High'].max()

    # The cup bottom must occur after the left lip
    cup_df = df.loc[left_lip_date:]
    if len(cup_df) < config.CUP_MIN_DURATION_DAYS:
        return None, None, None, "Not enough data after left lip to form a cup"

    cup_bottom_date = cup_df['Low'].idxmin()
    cup_bottom_price = cup_df['Low'].min()

    # Check cup depth
    if not left_lip_price >= cup_bottom_price * config.CUP_MIN_DEPTH_FACTOR:
        return None, None, None, f"Cup is not deep enough. Depth must be >{config.CUP_MIN_DEPTH_FACTOR}x"

    # Check cup duration
    cup_duration = (cup_bottom_date - left_lip_date).days
    if not (config.CUP_MIN_DURATION_DAYS <= cup_duration <= config.CUP_MAX_DURATION_DAYS):
        return None, None, None, f"Cup duration ({cup_duration} days) is out of range"

    # Find the right lip of the cup
    right_side_df = df.loc[cup_bottom_date:]
    if right_side_df.empty:
        return None, None, None, "No data available to form the right side of the cup"

    # The right lip should be close in price to the left lip
    price_match_upper = left_lip_price * config.CUP_LIP_MAX_DEVIATION
    price_match_lower = left_lip_price * config.CUP_LIP_MIN_DEVIATION

    potential_right_lips = right_side_df[right_side_df['High'].between(price_match_lower, price_match_upper)]
    if potential_right_lips.empty:
        return None, None, None, "Could not find a matching right lip for the cup"

    right_lip_date = potential_right_lips.index[0]
    right_lip_price = potential_right_lips['High'].iloc[0]

    # Verify a "U" shape by checking that the bottom is not too sharp
    cup_period_df = df.loc[left_lip_date:right_lip_date]
    low_points_count = cup_period_df[cup_period_df['Low'] < cup_bottom_price * 1.1].shape[0]
    if low_points_count < config.CUP_MIN_ROUNDED_POINTS:
         return None, None, None, f"Cup bottom is too sharp (V-shaped), not enough rounding ({low_points_count} points)"

    return left_lip_date, cup_bottom_date, right_lip_date, None


def _check_handle_formation(df, right_lip_date, cup_high_price):
    """
    Checks for the handle formation after the right lip of the cup.
    The handle is a slight pullback before the breakout.
    """
    handle_start_date = right_lip_date
    handle_lookahead_end_date = handle_start_date + dt.timedelta(days=config.HANDLE_MAX_DURATION_DAYS)
    handle_df = df.loc[handle_start_date:handle_lookahead_end_date]

    if handle_df.empty or len(handle_df) < config.HANDLE_MIN_DURATION_DAYS:
        return None, None, "Not enough data to form a handle"

    # Handle should be a shallow pullback from the right lip's high
    handle_pullback_max_price = cup_high_price * config.HANDLE_DEPTH_MAX_FACTOR
    handle_pullback_min_price = cup_high_price * config.HANDLE_DEPTH_MIN_FACTOR

    pullback_df = handle_df[handle_df['Low'] < handle_pullback_max_price]
    if pullback_df.empty:
        # If no pullback, it might be breaking out directly. Pivot is the cup high.
        return right_lip_date, cup_high_price, "No classic handle pullback found; watching for breakout from lip"

    handle_low_date = pullback_df['Low'].idxmin()
    handle_duration = (handle_low_date - right_lip_date).days

    if not (config.HANDLE_MIN_DURATION_DAYS <= handle_duration <= config.HANDLE_MAX_DURATION_DAYS):
        return None, None, f"Handle duration ({handle_duration} days) is out of range"

    # The handle's low should not be too deep
    handle_low_price = pullback_df['Low'].min()
    if handle_low_price < handle_pullback_min_price:
        return None, None, f"Handle pullback is too deep ({handle_low_price:.2f} vs min {handle_pullback_min_price:.2f})"

    # The pivot point for the breakout is the high of the right lip
    pivot_price = cup_high_price
    return handle_low_date, pivot_price, None


def _check_pivot_breakout(df, handle_low_date, pivot_price):
    """Checks for a breakout above the pivot point with high volume."""
    breakout_lookahead_end_date = handle_low_date + dt.timedelta(days=config.PIVOT_LOOKAHEAD_DAYS)

    # Look for breakout in the days following the handle's low
    pivot_df = df.query('index > @handle_low_date and index <= @breakout_lookahead_end_date and High >= @pivot_price')

    if pivot_df.empty:
        return False, "No pivot breakout within the lookahead period"

    # Check for volume breakout on the first day it crosses the pivot
    breakout_day = pivot_df.iloc[0]
    # Ensure we have a valid index for volume lookup
    if breakout_day.name in df.index:
        mean_volume_50d = df['Volume'].rolling(window=50).mean().loc[breakout_day.name]
        if pd.notna(mean_volume_50d) and breakout_day['Volume'] > mean_volume_50d * config.VOLUME_BREAKOUT_FACTOR:
            return True, f"Pattern detected with volume breakout on {pivot_df.index[0].date()}"

    return False, "Pivot breakout occurred but without sufficient volume"


def check_cup_with_handle(df_hist):
    """
    Checks for a Cup With Handle (CWH) chart pattern with a more robust and redefined logic.

    Returns:
        A tuple containing:
        - status (str): "FAIL", "WATCH", or "BREAKOUT"
        - reason (str): A description of the result.
    """
    # Ensure data is sorted and has the required moving averages
    df = df_hist.sort_index()
    if 'MA50' not in df:
        df['MA50'] = df['Close'].rolling(window=50).mean()
    if 'MA200' not in df:
        df['MA200'] = df['Close'].rolling(window=200).mean()

    # Stage 1: Find a valid cup shape (left lip, bottom, right lip).
    left_lip_date, cup_bottom_date, right_lip_date, err = _find_cup_shape(df)
    if err:
        return "FAIL", f"Stage 1 (Cup Shape): {err}"

    # Stage 2: Check for a prior uptrend before the cup.
    is_uptrend, reason = _check_prior_uptrend(df, left_lip_date)
    if not is_uptrend:
        return "FAIL", f"Stage 2 (Prior Trend): {reason}"

    # The high of the cup is the higher of the two lips
    cup_high_price = max(df.loc[left_lip_date, 'High'], df.loc[right_lip_date, 'High'])

    # Stage 3: Check for the handle formation.
    handle_low_date, pivot_price, err = _check_handle_formation(df, right_lip_date, cup_high_price)
    if err and "No classic handle" not in err: # Allow to proceed if no handle, just watching
        return "FAIL", f"Stage 3 (Handle): {err}"

    # If no handle was found, the "handle_low_date" is the right lip.
    if handle_low_date is None:
        handle_low_date = right_lip_date
        pivot_price = cup_high_price
        reason = "Awaiting breakout from cup lip"
    else:
        reason = "Awaiting breakout from handle"


    # Stage 4: Look for a pivot breakout.
    is_breakout, breakout_reason = _check_pivot_breakout(df, handle_low_date, pivot_price)
    if not is_breakout:
        # Passed stages 1-3, but hasn't broken out yet.
        return "WATCH", reason

    # Passed all stages, including breakout.
    return "BREAKOUT", breakout_reason
