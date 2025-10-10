import yfinance as yf
import datetime as dt
import pandas as pd
from src.patterns import check_cup_with_handle, check_double_bottom, check_vcp
from src import config

def get_pivot_crossing_info(df, check_function):
    """
    A helper function to run a pattern check and extract the pivot crossing date.
    This is for analysis only.
    """
    status, reason, pattern_data = check_function(df.copy())

    if not pattern_data:
        return f"No pattern found by {check_function.__name__}."

    pivot_price = pattern_data.get('pivot')

    # Determine the start date for the breakout check based on the pattern type
    if pattern_data['type'] == 'CWH':
        start_date = pattern_data['points'].get('handle_low', (None, None))[0] or pattern_data['points']['cup_right_lip'][0]
    elif pattern_data['type'] == 'DB':
        start_date = pattern_data['points']['second_trough'][0]
    elif pattern_data['type'] == 'VCP':
        last_peak_date = pattern_data['points'][-1][1]
        start_date = df.loc[last_peak_date:].index[-1]
    else:
        return "Unknown pattern type."

    if not pivot_price or not start_date:
        return "Could not determine pivot price or start date from pattern data."

    # Replicate the core logic of _check_pivot_breakout to find the crossing date
    # We use the updated PIVOT_LOOKAHEAD_DAYS from the config
    breakout_lookahead_end_date = start_date + dt.timedelta(days=config.PIVOT_LOOKAHEAD_DAYS)
    pivot_df = df.query('index > @start_date and index <= @breakout_lookahead_end_date and High >= @pivot_price')

    if pivot_df.empty:
        return (
            f"Pattern Found: {pattern_data['type']} ({status})\n"
            f"  - Pivot Price: {pivot_price:.2f}\n"
            f"  - Result: Price has not yet crossed the pivot within the {config.PIVOT_LOOKAHEAD_DAYS}-day lookahead period."
        )

    breakout_date = pivot_df.index[0]

    # Use a fixed "today" for reproducible calculation based on the last data point
    today = df.index[-1]
    days_passed = (today - breakout_date).days

    return (
        f"Pattern Found: {pattern_data['type']} ({status})\n"
        f"  - Pivot Price: {pivot_price:.2f}\n"
        f"  - Pivot was first crossed on: {breakout_date.strftime('%Y-%m-%d')}\n"
        f"  - Today's date (last data point): {today.strftime('%Y-%m-%d')}\n"
        f"  - Days passed since pivot crossing: {days_passed} days.\n"
        f"  - Final Reason from screener: {reason}"
    )

def analyze_ticker(symbol):
    """
    Analyzes a single ticker to find how long it has been in a WATCH state.
    """
    print(f"--- Analyzing {symbol} with PIVOT_LOOKAHEAD_DAYS = {config.PIVOT_LOOKAHEAD_DAYS} ---")
    ticker = yf.Ticker(symbol)

    pattern_checks = [
        ("CWH", check_cup_with_handle, config.CWH_LOOKBACK_PERIOD),
        ("DB", check_double_bottom, config.DB_LOOKBACK_PERIOD),
        ("VCP", check_vcp, config.VCP_LOOKBACK_PERIOD),
    ]

    found_actionable_pattern = False
    for pattern_name, check_function, lookback_period in pattern_checks:
        hist_df = ticker.history(period=lookback_period)
        if hist_df.empty:
            print(f"Could not fetch data for {symbol} with lookback '{lookback_period}'.")
            continue
        hist_df.index = hist_df.index.tz_localize(None)

        result = get_pivot_crossing_info(hist_df, check_function)
        print(f"\nAnalysis for {pattern_name}:")
        print(result)
        if "Days passed" in result:
            found_actionable_pattern = True

    if not found_actionable_pattern:
        print(f"\n--> Conclusion: No patterns for {symbol} are currently in a state of crossing their pivot.")


if __name__ == "__main__":
    analyze_ticker("MMS")