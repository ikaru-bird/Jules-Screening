import yfinance as yf
from tqdm import tqdm
import logging
import time
import random
import pandas as pd

from src import config
from src.charting import generate_stock_chart
from src.criteria import (
    check_price,
    check_roe,
    check_quarterly_eps_growth,
    check_annual_eps_growth,
    check_annual_eps_yoy_growth,
)
from src.patterns import check_cup_with_handle, check_double_bottom, check_vcp

def run_screening(ticker_df):
    """
    Runs the full screening process on a DataFrame of tickers.

    For each ticker, it checks against a set of financial criteria and
    chart patterns. Qualified stocks are charted and saved to a results file.
    """
    qualified_stocks = []

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=config.LOG_FILE,
        filemode='w' # Overwrite log file each run
    )

    print(f"Starting screening for {len(ticker_df)} candidate tickers...")
    logging.info(f"Screening initiated for {len(ticker_df)} tickers.")

    # Use itertuples for efficient iteration over DataFrame rows
    for stock in tqdm(ticker_df.itertuples(), total=len(ticker_df), desc="Screening Stocks"):
        symbol = stock.Ticker
        try:
            # Prepare stock data object to pass around
            stock_data = {
                'ticker': symbol,
                'name': stock.Name,
                'sector': stock.Sector,
                'industry': stock.Industry
            }

            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or info.get('marketCap') is None:
                logging.warning(f"Skipping {symbol}: Insufficient data from yfinance.")
                continue

            # --- Apply Screening Criteria ---
            criteria_to_check = [
                ("ROE", check_roe, info),
                ("EPS Annual Growth", check_annual_eps_growth, ticker),
                ("EPS 3Y Avg.Growth", check_annual_eps_yoy_growth, ticker),
                ("EPS Quarterly Growth", check_quarterly_eps_growth, ticker),
            ]

            criteria_results = []
            passed_count = 0
            all_financials_ok = True

            for name, check_func, arg in criteria_to_check:
                is_ok, reason = check_func(arg)
                criteria_results.append((name, is_ok, reason))
                if is_ok:
                    passed_count += 1

                # The first check that fails is enough to disqualify the stock, unless data is unavailable
                if not is_ok and reason != "--":
                    logging.info(f"Skipping {symbol}: Failed financial check '{name}'. Reason: {reason}")
                    all_financials_ok = False
                    break

            # Add results to stock_data to be passed to the chart generator
            stock_data['criteria_results'] = criteria_results
            stock_data['criteria_passed_count'] = passed_count

            if not all_financials_ok:
                continue

            # --- Apply Chart Pattern Analysis ---
            pattern_checks = [
                ("CWH", check_cup_with_handle, config.CWH_LOOKBACK_PERIOD),
                ("DB", check_double_bottom, config.DB_LOOKBACK_PERIOD),
                ("VCP", check_vcp, config.VCP_LOOKBACK_PERIOD),
            ]

            pattern_found = False
            for pattern_name, check_function, lookback_period in pattern_checks:
                # Fetch data using the specific lookback period for the pattern
                hist_df = ticker.history(period=lookback_period)
                if hist_df.empty:
                    logging.warning(f"Skipping {pattern_name} for {symbol}: No data for lookback '{lookback_period}'.")
                    continue
                hist_df.index = hist_df.index.tz_localize(None)

                status, reason, pattern_data = check_function(hist_df.copy())

                if status != "FAIL":
                    logging.info(f"MATCH ({status} / {pattern_name}): {symbol}. Reason: {reason}")
                    print(f"\nMATCH ({status} / {pattern_name}): {symbol} - {reason}")

                    qualified_stocks.append({
                        'Ticker': symbol,
                        'Name': stock.Name,
                        'Sector': stock.Sector,
                        'Industry': stock.Industry,
                        'Status': f"{status} ({pattern_name})",
                        'Reason': reason
                    })

                    print(f"Generating chart for {symbol} ({status} / {pattern_name})...")
                    generate_stock_chart(stock_data, f"{status}_{pattern_name}", pattern_data)

                    pattern_found = True
                    break # Stop after the first matching pattern

            if not pattern_found:
                logging.info(f"Skipping {symbol}: No qualifying chart patterns found.")
                continue

            time.sleep(random.uniform(1, 3))

        except Exception as e:
            logging.error(f"Could not process {symbol}: {e}", exc_info=True)
            continue

    # --- Save Results ---
    if qualified_stocks:
        results_df = pd.DataFrame(qualified_stocks)
        results_df.to_csv(config.RESULTS_FILE, index=False)
        print(f"\nScreening complete. Found {len(qualified_stocks)} stocks to watch or that broke out.")
        print(f"Final list saved to {config.RESULTS_FILE}")
        print("Charts for these stocks have been generated in the root directory.")
    else:
        print("\nScreening complete. No stocks met all the criteria.")

    return qualified_stocks
