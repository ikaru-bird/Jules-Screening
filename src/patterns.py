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

    breakout_date = pivot_df.index[0]
    one_month_ago = dt.datetime.now() - dt.timedelta(days=30)
    if breakout_date < one_month_ago:
        return False, f"Breakout on {breakout_date.date()} is older than 1 month"

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


def _check_prior_downtrend(df, first_trough_date):
    """
    Checks for a significant downtrend prior to the Double Bottom formation.
    The price should have dropped by at least DB_DOWNTREND_MIN_DROP_FACTOR.
    """
    downtrend_start_date = first_trough_date - dt.timedelta(days=config.DB_DOWNTREND_LOOKBACK_DAYS)
    downtrend_df = df.loc[downtrend_start_date:first_trough_date]

    if downtrend_df.empty:
        return False, "Not enough data for downtrend check"

    start_price = downtrend_df['High'].iloc[0]
    end_price = df.loc[first_trough_date, 'Low']

    if start_price >= end_price * config.DB_DOWNTREND_MIN_DROP_FACTOR:
        return True, "Prior downtrend confirmed"
    else:
        return False, f"Price did not drop enough in the {config.DB_DOWNTREND_LOOKBACK_DAYS} days prior to the first trough"


def _check_trough_roundness(df, trough_date, trough_price):
    """
    Checks if a trough has a rounded bottom.
    """
    trough_period_start = trough_date - dt.timedelta(days=10)
    trough_period_end = trough_date + dt.timedelta(days=10)
    trough_df = df.loc[trough_period_start:trough_period_end]

    if trough_df.empty:
        return True, "Not enough data for roundness check" # Assume OK if not enough data

    low_points_count = trough_df[trough_df['Low'] < trough_price * 1.05].shape[0]

    if low_points_count < config.DB_MIN_ROUNDED_POINTS:
        return False, f"Trough at {trough_date.date()} is too sharp (V-shaped), not enough rounding ({low_points_count} points)"

    return True, None


def _find_double_bottom_shape(df):
    """
    Identifies a valid Double Bottom shape (W-shape).
    """
    if len(df) < config.DB_DURATION_MIN_DAYS:
        return None, None, None, None, "Not enough historical data"

    # Find the first trough (lowest point in the first half of the period)
    first_half_df = df.iloc[:int(len(df) * 0.75)]
    if first_half_df.empty:
        return None, None, None, None, "Not enough data for first trough"
    first_trough_date = first_half_df['Low'].idxmin()
    first_trough_price = first_half_df['Low'].min()

    # Check roundness of the first trough
    is_rounded, reason = _check_trough_roundness(df, first_trough_date, first_trough_price)
    if not is_rounded:
        return None, None, None, None, reason

    # Define a search period for the peak, which must occur after the first trough
    peak_search_start_date = first_trough_date + dt.timedelta(days=5) # Allow some time to rise
    peak_search_end_date = first_trough_date + dt.timedelta(days=config.DB_DURATION_MAX_DAYS / 2)
    peak_search_df = df.loc[peak_search_start_date:peak_search_end_date]

    if peak_search_df.empty:
        return None, None, None, None, "No data to search for a peak"

    peak_date = peak_search_df['High'].idxmax()
    peak_price = peak_search_df['High'].max()

    # The peak must be a significant rise from the first trough
    if not peak_price >= first_trough_price * config.DB_PEAK_MIN_RISE_FACTOR:
        return None, None, None, None, f"Peak at {peak_date.date()} is not high enough relative to the first trough."

    # Find the second trough, which must occur after the peak
    second_trough_search_start_date = peak_date + dt.timedelta(days=5)
    second_trough_search_df = df.loc[second_trough_search_start_date:]

    if second_trough_search_df.empty:
        return None, None, None, None, "No data after peak to find second trough"

    second_trough_date = second_trough_search_df['Low'].idxmin()
    second_trough_price = second_trough_search_df['Low'].min()

    # Check roundness of the second trough
    is_rounded, reason = _check_trough_roundness(df, second_trough_date, second_trough_price)
    if not is_rounded:
        return None, None, None, None, reason

    # The two troughs must be close in price
    if not (second_trough_price <= first_trough_price * config.DB_TROUGH_MAX_DEVIATION and \
            second_trough_price >= first_trough_price / config.DB_TROUGH_MAX_DEVIATION):
        return None, None, None, None, f"Troughs are not at a similar price level ({first_trough_price:.2f} vs {second_trough_price:.2f})"

    # Check duration between troughs
    duration = (second_trough_date - first_trough_date).days
    if not (config.DB_DURATION_MIN_DAYS <= duration <= config.DB_DURATION_MAX_DAYS):
        return None, None, None, None, f"Duration between troughs ({duration} days) is out of range"

    return first_trough_date, peak_date, second_trough_date, peak_price, None


def check_double_bottom(df_hist):
    """
    Checks for a Double Bottom (DB) chart pattern.
    """
    df = df_hist.sort_index()

    first_trough_date, peak_date, second_trough_date, pivot_price, err = _find_double_bottom_shape(df)
    if err:
        return "FAIL", f"Stage 1 (W-Shape): {err}"

    is_downtrend, reason = _check_prior_downtrend(df, first_trough_date)
    if not is_downtrend:
        return "FAIL", f"Stage 2 (Prior Trend): {reason}"

    is_breakout, breakout_reason = _check_pivot_breakout(df, second_trough_date, pivot_price)
    if is_breakout:
        return "BREAKOUT", breakout_reason

    last_close = df['Close'].iloc[-1]
    if last_close >= pivot_price * config.DB_PIVOT_PROXIMITY_FACTOR:
        return "WATCH", f"Price consolidating near pivot point of {pivot_price:.2f}"

    return "FAIL", "W-shape formed but price is not near pivot"


def _find_vcp_contractions(df):
    """
    Identifies a series of volatility contractions (VCP).
    """
    if df.empty:
        return None, None, "No data for VCP"

    initial_high_price = df['High'].max()
    initial_high_date = df['High'].idxmax()

    contractions = []
    current_date = initial_high_date

    for i, expected_contraction in enumerate(config.VCP_CONTRACTIONS):
        search_df = df.loc[current_date:]
        if search_df.empty or len(search_df) < 5:
            return None, None, f"Not enough data to find contraction {i+1}"

        trough_date = search_df['Low'].idxmin()
        trough_price = search_df['Low'].min()

        contraction_depth = (initial_high_price - trough_price) / initial_high_price

        if not (expected_contraction / config.VCP_CONTRACTION_MAX_DEVIATION <= contraction_depth <= expected_contraction * config.VCP_CONTRACTION_MAX_DEVIATION):
            return None, None, f"Contraction {i+1} depth ({contraction_depth:.2%}) is out of range for expected {expected_contraction:.2%}"

        contractions.append({'trough_date': trough_date, 'depth': contraction_depth})

        recovery_df = df.loc[trough_date:]
        if recovery_df.empty:
            return None, None, "No data after last trough"

        peak_date = recovery_df['High'].idxmax()

        if recovery_df['High'].max() > initial_high_price * 1.03:
             return None, None, "Price broke out prematurely"

        current_date = peak_date

    final_tightening_df = df.loc[current_date:]
    if final_tightening_df.empty or len(final_tightening_df) > config.VCP_TIGHTENING_MAX_DAYS:
        return None, None, "Final consolidation is too long or no data"

    pivot_price = initial_high_price
    last_date = final_tightening_df.index[-1]

    return last_date, pivot_price, None


def check_vcp(df_hist):
    """
    Checks for a Volatility Contraction Pattern (VCP).
    """
    df = df_hist.sort_index()
    if 'MA50' not in df:
        df['MA50'] = df['Close'].rolling(window=50).mean()
    if 'MA200' not in df:
        df['MA200'] = df['Close'].rolling(window=200).mean()

    last_date, pivot_price, err = _find_vcp_contractions(df)
    if err:
        return "FAIL", f"Stage 1 (Contractions): {err}"

    if df.empty:
        return "FAIL", "No data for VCP"
    vcp_start_date = df['High'].idxmax()
    is_uptrend, reason = _check_prior_uptrend(df, vcp_start_date)
    if not is_uptrend:
        return "FAIL", f"Stage 2 (Prior Trend): {reason}"

    is_breakout, breakout_reason = _check_pivot_breakout(df, last_date, pivot_price)
    if not is_breakout:
        return "WATCH", "Awaiting breakout from VCP consolidation"

    return "BREAKOUT", breakout_reason