import yfinance as yf
import pandas as pd
import datetime as dt
from src import config
from src import patterns

def trace_cwh_for_ticker(symbol):
    """
    Fetches data for a single ticker and traces the CWH pattern recognition logic,
    printing out key variables at each decision point.
    """
    print(f"--- Tracing CWH Logic for Ticker: {symbol} ---")

    # 1. Fetch Data
    try:
        df_hist = yf.Ticker(symbol).history(period=config.CWH_LOOKBACK_PERIOD, interval="1d")
        if df_hist.empty:
            print(f"Error: No historical data found for {symbol}")
            return
        df = df_hist.sort_index()
        print(f"\nSuccessfully fetched {len(df)} days of data from {df.index.min().date()} to {df.index.max().date()}.")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # 2. Re-run the logic step-by-step to show the internal calculations.
    print("\n--- Detailed Analysis Trace ---")

    # Stage 1: Find a valid cup shape
    print("\n[Stage 1: Finding Cup Shape]")
    left_lip_date, cup_bottom_date, cup_bottom_price, right_lip_date, err = patterns._find_cup_shape(df)

    if err:
        print(f"Result: FAIL. Reason: {err}")
        return

    left_lip_price = df.loc[left_lip_date, 'High']
    print(f"  - Left Lip Date: {left_lip_date.date()} at ${left_lip_price:.2f}")
    print(f"  - Cup Bottom Date: {cup_bottom_date.date()} at ${cup_bottom_price:.2f}")
    print(f"  - Right Lip Date: {right_lip_date.date()} at ${df.loc[right_lip_date, 'High']:.2f}")
    print(f"  - Cup Duration: {(cup_bottom_date - left_lip_date).days} days (Required: {config.CUP_MIN_DURATION_DAYS}-{config.CUP_MAX_DURATION_DAYS})")
    print(f"  - Cup Depth Factor: {left_lip_price / cup_bottom_price:.2f}x (Required: >= {config.CUP_MIN_DEPTH_FACTOR}x)")
    print("  Result: OK. A valid cup shape was found.")

    # Stage 2: Check for a prior uptrend
    print("\n[Stage 2: Checking Prior Uptrend]")
    is_uptrend, trend_reason = patterns._check_prior_uptrend(df, left_lip_date)
    print(f"  - {trend_reason}")
    if not is_uptrend:
        print("  Result: FAIL.")
        return
    print("  Result: OK. Prior uptrend confirmed.")

    # Stage 3: Check for the handle formation
    print("\n[Stage 3: Checking Handle Formation]")
    cup_high_price = max(df.loc[left_lip_date, 'High'], df.loc[right_lip_date, 'High'])
    print(f"  - Cup High (Pivot Point): ${cup_high_price:.2f}")

    # Re-implementing handle check logic here to show details
    handle_start_date = right_lip_date
    handle_lookahead_end_date = handle_start_date + dt.timedelta(days=config.HANDLE_MAX_DURATION_DAYS)
    handle_df = df.loc[handle_start_date:handle_lookahead_end_date]
    pullback_df = handle_df[handle_df['Low'] < cup_high_price]

    if pullback_df.empty:
        print("  - No classic handle pullback found.")
        handle_low_date = right_lip_date
    else:
        handle_low_date = pullback_df['Low'].idxmin()
        handle_low_price = pullback_df['Low'].min()
        handle_duration = (handle_low_date - right_lip_date).days
        cup_depth = cup_high_price - cup_bottom_price
        min_handle_low = cup_high_price - (cup_depth / 3)

        print(f"  - Handle found from {right_lip_date.date()} to {handle_low_date.date()}")
        print(f"  - Handle Duration: {handle_duration} days (Max: {config.HANDLE_MAX_DURATION_DAYS})")
        print(f"  - Handle Low Price: ${handle_low_price:.2f}")
        print(f"  - Cup Depth (High - Bottom): ${cup_depth:.2f}")
        print(f"  - Max Allowable Pullback (1/3 of Depth): ${cup_depth/3:.2f}")
        print(f"  - Minimum Allowable Handle Low (High - 1/3 Depth): ${min_handle_low:.2f}")

        if handle_low_price < min_handle_low:
             print("  Result: FAIL. Handle pullback is too deep.")
             return
        else:
             print("  Result: OK. Handle depth is within the 1/3 limit.")

    # Stage 4: Look for a pivot breakout
    print("\n[Stage 4: Checking for Pivot Breakout]")
    is_breakout, breakout_reason = patterns._check_pivot_breakout(df, handle_low_date, cup_high_price)
    print(f"  - {breakout_reason}")
    if is_breakout:
        print("  Result: BREAKOUT DETECTED.")
    else:
        print("  Result: Awaiting breakout.")

    # Final Verdict from the original function
    print("\n--- FINAL SCRIPT VERDICT ---")
    status, reason = patterns.check_cup_with_handle(df)
    print(f"The script classified KD as: {status} ({reason})")


if __name__ == "__main__":
    trace_cwh_for_ticker('KD')