import pandas as pd
import yfinance as yf
from tqdm import tqdm
import logging
import time
from generate_chart import generate_stock_chart

# --- Setup ---
# Configure logging to capture errors and progress
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='screener.log')

# Constants for screening criteria
MIN_ROE = 0.15
MIN_Q_EPS_GROWTH = 0.25
MIN_ANNUAL_EPS_GROWTH_CAGR = 0.25
MAX_PCT_AWAY_FROM_52W_HIGH = 0.25

# --- Helper Functions ---

def check_roe(ticker_info):
    """Checks if the Return on Equity is above the minimum threshold."""
    try:
        roe = ticker_info.get('returnOnEquity')
        if roe is not None and roe >= MIN_ROE:
            return True, roe
        return False, roe
    except Exception:
        return False, None

def check_quarterly_eps_growth(ticker):
    """Checks if the most recent quarterly EPS has grown sufficiently YoY."""
    try:
        q_earnings = ticker.quarterly_earnings
        if len(q_earnings) < 5:
            return False, "Not enough quarterly data"

        # Ensure earnings are positive to avoid misleading growth percentages
        latest_eps = q_earnings['Earnings'].iloc[-1]
        eps_year_ago = q_earnings['Earnings'].iloc[-5]

        if eps_year_ago > 0:
            growth = (latest_eps - eps_year_ago) / eps_year_ago
            if growth >= MIN_Q_EPS_GROWTH:
                return True, growth
        return False, "Negative or zero base EPS"
    except Exception:
        return False, "Error fetching/calculating"

def check_accelerating_eps_growth(ticker):
    """Checks if the YoY quarterly EPS growth is accelerating."""
    try:
        q_earnings = ticker.quarterly_earnings
        if len(q_earnings) < 6: # Need at least 6 quarters for two YoY comparisons
            return False, "Not enough data for acceleration check"

        # Latest YoY growth
        latest_eps = q_earnings['Earnings'].iloc[-1]
        eps_year_ago_1 = q_earnings['Earnings'].iloc[-5]

        # Previous quarter's YoY growth
        prev_eps = q_earnings['Earnings'].iloc[-2]
        eps_year_ago_2 = q_earnings['Earnings'].iloc[-6]

        if eps_year_ago_1 > 0 and eps_year_ago_2 > 0:
            growth_latest = (latest_eps - eps_year_ago_1) / eps_year_ago_1
            growth_previous = (prev_eps - eps_year_ago_2) / eps_year_ago_2

            if growth_latest > growth_previous:
                return True, f"{growth_latest:.2f} > {growth_previous:.2f}"

        return False, "Negative base EPS or other issue"
    except Exception:
        return False, "Error during acceleration check"

def check_annual_eps_growth(ticker):
    """
    Checks if the 3-year average annual EPS growth (CAGR) is sufficient.
    This now uses Net Income and Shares Outstanding due to 'earnings' deprecation.
    """
    try:
        # Get annual financial statements
        financials = ticker.financials
        if financials.shape[1] < 4:
            return False, "Not enough annual financial data"

        # BasicDilutedEPS is available in financials
        # Let's check if we can use it directly. It is often more reliable.
        if 'Basic EPS' in financials.index:
            eps_data = financials.loc['Basic EPS'].dropna()
            if len(eps_data) < 4:
                 # Fallback to Net Income if Basic EPS is not sufficient
                 pass
            else:
                eps_start = eps_data.iloc[-4]
                eps_end = eps_data.iloc[-1]

                if eps_start > 0 and eps_end > 0:
                    cagr = ((eps_end / eps_start) ** (1/3)) - 1
                    if cagr >= MIN_ANNUAL_EPS_GROWTH_CAGR:
                        return True, cagr
                return False, "Negative or zero base EPS for CAGR"

        # Fallback to calculating from Net Income if 'Basic EPS' is not there or fails
        net_income = financials.loc['Net Income'].dropna()

        # Getting shares outstanding can be tricky as it changes.
        # As a proxy, we'll use the basic average shares from the income statement.
        if 'Basic Average Shares' not in financials.index:
             return False, "Cannot find share count to calculate EPS"

        shares = financials.loc['Basic Average Shares'].dropna()

        # Align data and calculate EPS
        common_idx = net_income.index.intersection(shares.index)
        if len(common_idx) < 4:
             return False, "Not enough data points for Net Income/Shares"

        eps = (net_income[common_idx] / shares[common_idx])

        eps_start = eps.iloc[-4]
        eps_end = eps.iloc[-1]

        if eps_start > 0 and eps_end > 0:
            cagr = ((eps_end / eps_start) ** (1/3)) - 1
            if cagr >= MIN_ANNUAL_EPS_GROWTH_CAGR:
                return True, cagr
        return False, "Negative or zero base EPS for CAGR"

    except (KeyError, IndexError, Exception):
        return False, "Error fetching/calculating annual EPS growth"

def check_buy_point(ticker):
    """Checks if the current price is near the 52-week high."""
    try:
        hist = ticker.history(period="1y")
        if hist.empty:
            return False, "No history data"

        high_52wk = hist['High'].max()
        current_price = hist['Close'].iloc[-1]

        if current_price >= high_52wk * (1 - MAX_PCT_AWAY_FROM_52W_HIGH):
            return True, current_price
        return False, "Not near 52-week high"
    except Exception:
        return False, "Error fetching/calculating"

def get_financial_summary(ticker):
    """Gets the last 4 quarters of revenue and EPS."""
    try:
        q_financials = ticker.quarterly_financials
        q_earnings = ticker.quarterly_earnings

        # Get last 4 quarters of revenue and EPS
        revenue = q_financials.loc['Total Revenue'].iloc[-4:].to_list()
        eps = q_earnings['Earnings'].iloc[-4:].to_list()

        # Note: Beat/Miss data is not reliably available via yfinance.
        # This will be omitted from the final chart.
        return {"revenue": revenue, "eps": eps}
    except Exception:
        return {"revenue": [], "eps": []}


# --- Main Screening Logic ---

def run_screening(tickers):
    """Runs the screening process for a given list of tickers."""
    qualified_stocks = []

    # Using tqdm for a progress bar
    for symbol in tqdm(tickers, desc="Screening Stocks"):
        try:
            ticker = yf.Ticker(symbol)
            ticker_info = ticker.info

            # Pre-filter: skip if no info or basic data is missing
            if not ticker_info or 'returnOnEquity' not in ticker_info or 'sector' not in ticker_info:
                logging.info(f"Skipping {symbol}: Insufficient basic info.")
                continue

            # 1. Check ROE
            roe_ok, roe_val = check_roe(ticker_info)
            if not roe_ok:
                continue

            # 2. Check Quarterly EPS Growth
            q_eps_ok, _ = check_quarterly_eps_growth(ticker)
            if not q_eps_ok:
                continue

            # 3. Check Annual EPS Growth
            a_eps_ok, _ = check_annual_eps_growth(ticker)
            if not a_eps_ok:
                continue

            # 4. Check for Accelerating EPS Growth (Desirable, not mandatory)
            eps_accel_ok, _ = check_accelerating_eps_growth(ticker)
            # This is a "nice to have", so we don't 'continue' if it fails.
            # We can perhaps use this info later to rank results.

            # 5. Check Buy Point
            buy_point_ok, price = check_buy_point(ticker)
            if not buy_point_ok:
                continue

            # If all checks pass, gather info and add to list
            logging.info(f"QUALIFIED: {symbol} (EPS Accel: {eps_accel_ok})")

            summary = get_financial_summary(ticker)

            qualified_stocks.append({
                'Ticker': symbol,
                'Name': ticker_info.get('longName', 'N/A'),
                'Sector': ticker_info.get('sector', 'N/A'),
                'Price': price,
                'ROE': roe_val,
                'QuarterlyRevenue': summary['revenue'],
                'QuarterlyEPS': summary['eps']
            })

            # --- Generate Chart for Qualified Stock ---
            print(f"Generating chart for qualified stock: {symbol}")
            try:
                generate_stock_chart(symbol)
                # Be polite to the API server
                time.sleep(2)
            except Exception as e:
                logging.error(f"Could not generate chart for {symbol}: {e}")


        except Exception as e:
            logging.error(f"Could not process {symbol}: {e}")
            continue

    return qualified_stocks

if __name__ == '__main__':
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Stock screener")
    parser.add_argument("--start", type=int, default=0, help="Starting index of the ticker list to process")
    parser.add_argument("--end", type=int, default=-1, help="Ending index of the ticker list to process")
    args = parser.parse_args()

    # Load tickers from the CSV file
    try:
        full_ticker_list = pd.read_csv('tickers.csv', header=None)[0].tolist()
    except FileNotFoundError:
        print("tickers.csv not found. Please run process_tickers.py first.")
        exit()

    # Slice the list based on arguments
    if args.end == -1:
        end_index = len(full_ticker_list)
    else:
        end_index = args.end

    ticker_list_subset = full_ticker_list[args.start:end_index]

    print(f"Starting screening for tickers from index {args.start} to {end_index} ({len(ticker_list_subset)} tickers)...")

    # Run the main screening function
    results = run_screening(ticker_list_subset)

    # Save results to a CSV file (append mode)
    output_file = 'screening_results.csv'
    if results:
        results_df = pd.DataFrame(results)
        # Check if file exists to determine if we need to write headers
        file_exists = os.path.exists(output_file)
        results_df.to_csv(output_file, mode='a', index=False, header=not file_exists)

        print(f"\nBatch complete. Found {len(results)} qualified stocks in this batch.")
        print(f"Results appended to {output_file}")
    else:
        print("\nBatch complete. No stocks met all criteria in this batch.")
