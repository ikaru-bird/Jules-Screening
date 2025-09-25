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
            criteria_checks = [
                check_price(info),
                check_roe(info),
                check_quarterly_eps_growth(ticker),
                check_annual_eps_growth(ticker)
            ]

            all_financials_ok = True
            for is_ok, reason in criteria_checks:
                if not is_ok:
                    logging.info(f"Skipping {symbol}: Failed financial check. Reason: {reason}")
                    all_financials_ok = False
                    break
            if not all_financials_ok:
                continue

            # --- Apply Chart Pattern Analysis ---
            hist_df = ticker.history(period="2y")
            hist_df.index = hist_df.index.tz_localize(None)

            pattern_checks = [
                ("CWH", check_cup_with_handle),
                ("DB", check_double_bottom),
                ("VCP", check_vcp),
            ]

            pattern_found = False
            for pattern_name, check_function in pattern_checks:
                status, reason = check_function(hist_df.copy())

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
                    generate_stock_chart(stock_data, f"{status}_{pattern_name}")

                    pattern_found = True
                    break

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
