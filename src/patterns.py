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
        return None, None, None, None, "Not enough historical data to form a cup"

    # Find the high point (left lip) in the first 75% of the lookback period
    left_side_df = df.iloc[:int(len(df) * 0.75)]
    left_lip_date = left_side_df['High'].idxmax()
    left_lip_price = left_side_df['High'].max()

    # The cup bottom must occur after the left lip, within a reasonable timeframe
    cup_search_end_date = left_lip_date + dt.timedelta(days=config.CUP_MAX_DURATION_DAYS)
    cup_df = df.loc[left_lip_date:cup_search_end_date]
    if len(cup_df) < config.CUP_MIN_DURATION_DAYS:
        return None, None, None, None, "Not enough data after left lip to form a cup"

    cup_bottom_date = cup_df['Low'].idxmin()
    cup_bottom_price = cup_df['Low'].min()

    # Check cup depth
    if not left_lip_price >= cup_bottom_price * config.CUP_MIN_DEPTH_FACTOR:
        return None, None, None, None, f"Cup is not deep enough. Depth must be >{config.CUP_MIN_DEPTH_FACTOR}x"

    # Check cup duration
    cup_duration = (cup_bottom_date - left_lip_date).days
    if not (config.CUP_MIN_DURATION_DAYS <= cup_duration <= config.CUP_MAX_DURATION_DAYS):
        return None, None, None, None, f"Cup duration ({cup_duration} days) is out of range"

    # Find the right lip of the cup
    right_side_df = df.loc[cup_bottom_date:]
    if right_side_df.empty:
        return None, None, None, None, "No data available to form the right side of the cup"

    # The right lip should be close in price to the left lip
    price_match_upper = left_lip_price * config.CUP_LIP_MAX_DEVIATION
    price_match_lower = left_lip_price * config.CUP_LIP_MIN_DEVIATION

    potential_right_lips = right_side_df[right_side_df['High'].between(price_match_lower, price_match_upper)]
    if potential_right_lips.empty:
        return None, None, None, None, "Could not find a matching right lip for the cup"

    right_lip_date = potential_right_lips.index[0]
    right_lip_price = potential_right_lips['High'].iloc[0]

    # Verify a "U" shape by checking that the bottom is not too sharp
    cup_period_df = df.loc[left_lip_date:right_lip_date]
    low_points_count = cup_period_df[cup_period_df['Low'] < cup_bottom_price * 1.1].shape[0]
    if low_points_count < config.CUP_MIN_ROUNDED_POINTS:
         return None, None, None, None, f"Cup bottom is too sharp (V-shaped), not enough rounding ({low_points_count} points)"

    return left_lip_date, cup_bottom_date, cup_bottom_price, right_lip_date, None


def _check_handle_formation(df, right_lip_date, cup_high_price, cup_bottom_price):
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
    pullback_df = handle_df[handle_df['Low'] < cup_high_price]
    if pullback_df.empty:
        # If no pullback, it might be breaking out directly. Pivot is the cup high.
        return right_lip_date, cup_high_price, "No classic handle pullback found; watching for breakout from lip"

    handle_low_date = pullback_df['Low'].idxmin()
    handle_duration = (handle_low_date - right_lip_date).days

    if not (config.HANDLE_MIN_DURATION_DAYS <= handle_duration <= config.HANDLE_MAX_DURATION_DAYS):
        return None, None, f"Handle duration ({handle_duration} days) is out of range"

    # The handle's low should not be too deep.
    # The pullback is not allowed to be more than 1/3rd of the cup's depth.
    handle_low_price = pullback_df['Low'].min()
    cup_depth = cup_high_price - cup_bottom_price
    min_handle_low_price = cup_high_price - (cup_depth / 3)

    if handle_low_price < min_handle_low_price:
        return None, None, f"Handle pullback is too deep. Low: {handle_low_price:.2f}, Min Allowable: {min_handle_low_price:.2f}"

    # Final check: Ensure the pattern hasn't broken down. The latest close must be above the handle's low.
    last_close = df['Close'].iloc[-1]
    if last_close < handle_low_price:
        return None, None, f"Pattern invalidated. Current price ({last_close:.2f}) is below handle low ({handle_low_price:.2f})"

    # The pivot point for the breakout is the high of the right lip
    pivot_price = cup_high_price
    return handle_low_date, pivot_price, None


def _check_pivot_breakout(df, handle_low_date, pivot_price):
    """
    Checks for a breakout above the pivot point with high volume.
    Returns a status, a reason, and the date of the breakout if found.
    """
    breakout_lookahead_end_date = handle_low_date + dt.timedelta(days=config.PIVOT_LOOKAHEAD_DAYS)

    # Look for the first day price crossed the pivot
    pivot_df = df.query('index > @handle_low_date and index <= @breakout_lookahead_end_date and High >= @pivot_price')

    if pivot_df.empty:
        return False, "NO_BREAKOUT", None

    breakout_date = pivot_df.index[0]
    breakout_day = pivot_df.iloc[0]
    one_month_ago = dt.datetime.now() - dt.timedelta(days=30)

    # Check for volume on the breakout day
    volume_ok = False
    if breakout_day.name in df.index:
        mean_volume_50d = df['Volume'].rolling(window=50).mean().loc[breakout_day.name]
        if pd.notna(mean_volume_50d) and breakout_day['Volume'] > mean_volume_50d * config.VOLUME_BREAKOUT_FACTOR:
            volume_ok = True

    # Evaluate based on volume and date
    if volume_ok:
        # High-volume breakout: success, unless it's old
        if breakout_date < one_month_ago:
            return False, f"OLD_BREAKOUT: Breakout on {breakout_date.date()} is older than 1 month", None
        return True, f"Pattern detected with volume breakout on {breakout_date.date()}", breakout_date
    else:
        # Low-volume crossing: potential WATCH, unless it's old
        if breakout_date < one_month_ago:
            return False, f"STALE_WATCH: Low-volume pivot cross on {breakout_date.date()} is older than 1 month", None
        return False, "Pivot breakout occurred but without sufficient volume", None


def check_cup_with_handle(df_hist):
    """
    Checks for a Cup With Handle (CWH) chart pattern.

    Returns:
        A tuple containing:
        - status (str): "FAIL", "WATCH", or "BREAKOUT"
        - reason (str): A description of the result.
        - pattern_data (dict): Contains pivot price and key points for charting.
    """
    # Ensure data is sorted and has the required moving averages
    df = df_hist.sort_index()
    if 'MA50' not in df:
        df['MA50'] = df['Close'].rolling(window=50).mean()
    if 'MA200' not in df:
        df['MA200'] = df['Close'].rolling(window=200).mean()

    # Stage 1: Find a valid cup shape (left lip, bottom, right lip).
    left_lip_date, cup_bottom_date, cup_bottom_price, right_lip_date, err = _find_cup_shape(df)
    if err:
        return "FAIL", f"Stage 1 (Cup Shape): {err}", None

    # Stage 2: Check for a prior uptrend before the cup.
    is_uptrend, reason = _check_prior_uptrend(df, left_lip_date)
    if not is_uptrend:
        return "FAIL", f"Stage 2 (Prior Trend): {reason}", None

    # Per user request, the pivot point is the high of the right lip (the start of the handle).
    # The handle pullback and depth checks are also relative to this price.
    cup_high_price = df.loc[right_lip_date, 'High']

    # Stage 3: Check for the handle formation.
    handle_low_date, returned_pivot, err = _check_handle_formation(df, right_lip_date, cup_high_price, cup_bottom_price)

    # The pivot price for a CWH is ALWAYS the high of the cup (the right lip, as per user request).
    # This ensures pivot_price is always set, even if no classic handle forms.
    pivot_price = cup_high_price
    if pivot_price is None:
        return "FAIL", "Could not determine pivot price", None

    # First, check for disqualifying errors from the handle formation.
    if err and "No classic handle" not in err:
        return "FAIL", f"Stage 3 (Handle): {err}", None

    # Determine the reason and handle details for charting
    handle_low_price = None
    current_reason = ""
    if err and "No classic handle" in err:
        current_reason = err # Use the specific reason from the function (e.g., "No classic handle pullback found...")
        # If no handle, the breakout check should start from the right lip
        handle_low_date = right_lip_date
    else: # A valid handle was found
        current_reason = "Awaiting breakout from handle"
        handle_low_price = df.loc[handle_low_date, 'Low']


    # Prepare data for charting. This is created regardless of WATCH or BREAKOUT status.
    pattern_data = {
        'type': 'CWH',
        'pivot': pivot_price,
        'pivot_date': right_lip_date,
        'points': {
            'cup_left_lip': (left_lip_date, df.loc[left_lip_date, 'High']),
            'cup_bottom': (cup_bottom_date, cup_bottom_price),
            'cup_right_lip': (right_lip_date, df.loc[right_lip_date, 'High']),
            # Only include handle_low if it was actually found
            'handle_low': (handle_low_date, handle_low_price) if handle_low_price is not None else None,
        }
    }

    # Stage 4: Look for a pivot breakout.
    is_breakout, breakout_reason, _ = _check_pivot_breakout(df, handle_low_date, pivot_price)
    if is_breakout:
        return "BREAKOUT", breakout_reason, pattern_data

    # If it didn't break out, check if it's because the breakout is old or stale.
    if "OLD_BREAKOUT" in breakout_reason or "STALE_WATCH" in breakout_reason:
        return "FAIL", breakout_reason, None

    # If breakout occurred without volume, status is WATCH.
    if "without sufficient volume" in breakout_reason:
        return "WATCH", breakout_reason, pattern_data

    # Otherwise, it's a valid pattern still forming and awaiting a breakout attempt.
    return "WATCH", current_reason, pattern_data


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

    Returns:
        A tuple containing:
        - status (str): "FAIL", "WATCH", or "BREAKOUT"
        - reason (str): A description of the result.
        - pattern_data (dict): Contains pivot price and key points for charting.
    """
    df = df_hist.sort_index()

    first_trough_date, peak_date, second_trough_date, pivot_price, err = _find_double_bottom_shape(df)
    if err:
        return "FAIL", f"Stage 1 (W-Shape): {err}", None

    is_downtrend, reason = _check_prior_downtrend(df, first_trough_date)
    if not is_downtrend:
        return "FAIL", f"Stage 2 (Prior Trend): {reason}", None

    # A valid W-shape was found, so prepare the data for charting.
    pattern_data = {
        'type': 'DB',
        'pivot': pivot_price,
        'pivot_date': peak_date,
        'points': {
            'first_trough': (first_trough_date, df.loc[first_trough_date, 'Low']),
            'peak': (peak_date, pivot_price), # The pivot is the peak's high
            'second_trough': (second_trough_date, df.loc[second_trough_date, 'Low']),
        }
    }

    is_breakout, breakout_reason, breakout_date = _check_pivot_breakout(df, second_trough_date, pivot_price)
    if is_breakout:
        # Add the breakout point to the pattern data for charting
        pattern_data['points']['breakout_point'] = (breakout_date, df.loc[breakout_date, 'High'])
        return "BREAKOUT", breakout_reason, pattern_data

    # If it didn't break out, check if it's because the breakout is old or stale.
    if "OLD_BREAKOUT" in breakout_reason or "STALE_WATCH" in breakout_reason:
        return "FAIL", breakout_reason, None

    # If a pivot cross occurred without sufficient volume, it's a WATCH.
    if "without sufficient volume" in breakout_reason:
        return "WATCH", breakout_reason, pattern_data

    # Check if price is still consolidating near the pivot; if so, it's a WATCH.
    last_close = df['Close'].iloc[-1]
    if last_close >= pivot_price * config.DB_PIVOT_PROXIMITY_FACTOR:
        return "WATCH", f"Price consolidating near pivot point of {pivot_price:.2f}", pattern_data

    # A valid W-shape was found, but the price has moved away from the pivot.
    # We return FAIL but include the data so it could potentially be charted for analysis.
    return "FAIL", "W-shape formed but price is not near pivot", pattern_data


def _find_vcp_contractions(df):
    """
    Identifies a series of volatility contractions (VCP).
    Returns the key points, the pivot price, and the last date for breakout checks.
    """
    if df.empty or len(df) < config.VCP_TIGHTENING_MAX_DAYS * len(config.VCP_CONTRACTIONS):
        return None, None, None, "Not enough data for VCP"

    # Start with the highest point in the entire lookback period
    overall_high_price = df['High'].max()
    overall_high_date = df['High'].idxmax()

    points = [('peak', overall_high_date, overall_high_price)]
    current_high_date = overall_high_date
    current_high_price = overall_high_price

    # Find the sequence of contractions
    for i, expected_contraction in enumerate(config.VCP_CONTRACTIONS):
        # Search for the next trough after the last high point
        trough_search_df = df.loc[current_high_date:]
        if trough_search_df.empty or len(trough_search_df) < 5:
            return None, None, None, f"Not enough data to find contraction trough {i+1}"

        trough_date = trough_search_df['Low'].idxmin()
        trough_price = trough_search_df['Low'].min()

        # Validate contraction depth against the initial high
        contraction_depth = (overall_high_price - trough_price) / overall_high_price
        if not (expected_contraction / config.VCP_CONTRACTION_MAX_DEVIATION <= contraction_depth <= expected_contraction * config.VCP_CONTRACTION_MAX_DEVIATION):
            return None, None, None, f"Contraction {i+1} depth ({contraction_depth:.2%}) is out of range for expected {expected_contraction:.2%}"
        points.append(('trough', trough_date, trough_price))

        # Search for the next peak after the trough
        # The next peak must be lower than the previous one and within the lookahead period of the trough
        peak_search_df = df.loc[trough_date : trough_date + dt.timedelta(days=90)]
        potential_peaks = peak_search_df[peak_search_df['High'] < current_high_price]

        if potential_peaks.empty:
            return None, None, None, f"Could not find a lower high for peak {i+1}"

        peak_date = potential_peaks['High'].idxmax()
        peak_price = potential_peaks['High'].max()

        # The new peak shouldn't be too low either, must show some recovery
        if peak_price < trough_price * 1.05:
            return None, None, None, f"Recovery peak {i+1} is not significant enough"
        points.append(('peak', peak_date, peak_price))

        current_high_date = peak_date
        current_high_price = peak_price

    # After all contractions, define the pivot and final consolidation area
    pivot_price = current_high_price # Pivot is the last peak found
    final_consolidation_df = df.loc[current_high_date:]

    if final_consolidation_df.empty or len(final_consolidation_df) > config.VCP_TIGHTENING_MAX_DAYS:
        return None, None, None, "Final consolidation is too long or no data"

    # The last date for the breakout check is the end of the data period we analyzed
    last_date = final_consolidation_df.index[-1]

    return points, pivot_price, last_date, None


def check_vcp(df_hist):
    """
    Checks for a Volatility Contraction Pattern (VCP).

    Returns:
        A tuple containing:
        - status (str): "FAIL", "WATCH", or "BREAKOUT"
        - reason (str): A description of the result.
        - pattern_data (dict): Contains pivot price and key points for charting.
    """
    df = df_hist.sort_index()
    if 'MA50' not in df:
        df['MA50'] = df['Close'].rolling(window=50).mean()
    if 'MA200' not in df:
        df['MA200'] = df['Close'].rolling(window=200).mean()

    # Stage 1: Find the VCP contractions and pivot point.
    points, pivot_price, last_date, err = _find_vcp_contractions(df)
    if err:
        return "FAIL", f"Stage 1 (Contractions): {err}", None

    # Stage 2: Check for a prior uptrend before the pattern started.
    if not points:
         return "FAIL", "Stage 1 (Contractions): No points found", None
    vcp_start_date = points[0][1] # Date of the first peak
    is_uptrend, reason = _check_prior_uptrend(df, vcp_start_date)
    if not is_uptrend:
        return "FAIL", f"Stage 2 (Prior Trend): {reason}", None

    # If pattern is found, prepare data for charting
    # The pivot date is the date of the last peak found.
    pivot_date = [p[1] for p in points if p[0] == 'peak'][-1]
    pattern_data = {
        'type': 'VCP',
        'pivot': pivot_price,
        'pivot_date': pivot_date,
        'points': points
    }

    # Stage 3: Look for a pivot breakout.
    is_breakout, breakout_reason, _ = _check_pivot_breakout(df, last_date, pivot_price)
    if is_breakout:
        return "BREAKOUT", breakout_reason, pattern_data

    # If it didn't break out, check if it's because the breakout is old or stale.
    if "OLD_BREAKOUT" in breakout_reason or "STALE_WATCH" in breakout_reason:
        return "FAIL", breakout_reason, None

    # If a pivot cross occurred without sufficient volume, it's a WATCH.
    if "without sufficient volume" in breakout_reason:
        return "WATCH", breakout_reason, pattern_data

    return "WATCH", "Awaiting breakout from VCP consolidation", pattern_data