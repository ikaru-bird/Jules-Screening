import pandas as pd
import yfinance as yf
from tqdm import tqdm
import logging
import time
from generate_chart import generate_stock_chart
import argparse
import random
import datetime as dt

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='screener.log')

# O'Neil / Minervini Criteria
MIN_ROE = 0.15
MIN_Q_EPS_GROWTH = 0.25
MIN_ANNUAL_EPS_GROWTH_CAGR = 0.25
MIN_PRICE = 10.00

# --- Helper Functions ---

def check_price(ticker_info):
    """Checks if the stock price is above the minimum threshold."""
    try:
        price = ticker_info.get('currentPrice')
        if price is not None and price >= MIN_PRICE:
            return True, price
        return False, price
    except Exception:
        return False, None

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
        if q_earnings is None or len(q_earnings) < 5:
            return False, "Not enough quarterly data"

        latest_eps = q_earnings['Earnings'].iloc[-1]
        eps_year_ago = q_earnings['Earnings'].iloc[-5]

        if eps_year_ago > 0:
            growth = (latest_eps - eps_year_ago) / eps_year_ago
            if growth >= MIN_Q_EPS_GROWTH:
                return True, growth
        return False, "Negative or zero base EPS"
    except Exception:
        return False, "Error fetching/calculating"

def check_annual_eps_growth(ticker):
    """Checks if the 3-year average annual EPS growth (CAGR) is sufficient."""
    try:
        financials = ticker.financials
        if financials is None or financials.shape[1] < 4:
            return False, "Not enough annual financial data"

        if 'Basic EPS' in financials.index:
            eps_data = financials.loc['Basic EPS'].dropna()
            if len(eps_data) >= 4:
                eps_start = eps_data.iloc[-4]
                eps_end = eps_data.iloc[-1]
                if eps_start > 0 and eps_end > 0:
                    cagr = ((eps_end / eps_start) ** (1/3)) - 1
                    if cagr >= MIN_ANNUAL_EPS_GROWTH_CAGR:
                        return True, cagr
        return False, "Could not calculate 3-year CAGR"
    except Exception:
        return False, "Error fetching/calculating annual EPS growth"

# ---------------------------------------#
# カップウィズハンドル判定処理 (from User)
# ---------------------------------------#
def check_cup_with_handle(df0):
    today = dt.date.today()
    alist = []
    dummy_dt = today

    # ①カップの開始
    rows = df0['Low']
    if len(df0.index) > 0:
        min_val = rows.min()
        idxmin = rows.idxmin()
    else:
        return False, "Empty history"

    # ②カップの頂点
    maxlim_dt = today - dt.timedelta(days=30)
    df1 = df0[idxmin:maxlim_dt]
    if len(df1.index) > 0:
        rows = df1['High']
        max_val = rows.max()
        idxmax = rows.idxmax()
        alist.append((idxmax, df0.loc[idxmax, "High"]))
    else:
        return False, "Cup top check failed (1)"

    if not max_val > min_val * 1.3:
        return False, "Cup top check failed (2)"

    # ③ベースの形成
    df1 = df0[idxmax:today]
    base_p1 = max_val * 0.67
    base_p2 = max_val * 0.88
    df2 = df1.query('@base_p1 <= Close <= @base_p2')

    if len(df2.index) > 0:
        base_sdt = df2.index[0]
        base_len = (df2.index[-1] - idxmax).days
        base_rate = df2.Close.std() / df2.Close.mean()
        df1_base = df0[base_sdt:df2.index[-1]]
        base_min = df1_base['Close'].min()
        base_max = df1_base['Close'].max()

        if not ((base_len >= 49) and (base_len <= 455) and (base_rate <= 0.05) and (base_min >= base_p1) and (base_max <= base_p2)):
            return False, "Base formation check failed"
    else:
        return False, "Base formation check failed (2)"

    # ④カップの形成
    cup_p1 = max_val * 0.95
    cup_p2 = max_val * 1.05
    base_edt1 = idxmax + dt.timedelta(days=49)
    base_edt2 = idxmax + dt.timedelta(days=455)
    df2 = df0.query('index >= @base_sdt & @base_edt1 <= index <= @base_edt2 & @cup_p1 <= High')

    if len(df2.index) > 0:
        cup_edt = df2.index[0]
        handle_edt1 = cup_edt
        handle_edt2 = cup_edt + dt.timedelta(days=60)
        df2_handle = df0.query('@handle_edt1 <= index <= @handle_edt2')
        if df2_handle.empty: return False, "Handle check failed (1)"

        handle_p0 = df2_handle['High'].max()
        cup_edt = df2_handle['High'].idxmax()
        handle_edt1 = cup_edt + dt.timedelta(days=5)
        handle_p1 = handle_p0 * 0.88
        handle_p2 = handle_p0 * 0.95
        df3 = df0.query('@handle_edt1 <= index <= @handle_edt2 & @handle_p1 <= Low <= @handle_p2 & MA50 <= Close')

        if len(df3.index) == 0:
            pvt_p = handle_p0
            if pvt_p > cup_p2:
                return False, "Handle check failed (2)"
        else:
            cwh_dt = df3['Low'].idxmin()
            pvt_p = handle_p0
    else:
        return False, "Cup formation check failed"

    # ⑥ピボット判定
    cwh_dtx = cwh_dt + dt.timedelta(days=30)
    df2_pivot = df0.query('@cwh_dt < index < @cwh_dtx & High >= @pvt_p')

    if len(df2_pivot.index) > 0:
        # Check for volume breakout
        breakout_day = df2_pivot.iloc[0]
        mean_volume_50d = df0['Volume'].rolling(window=50).mean().iloc[-1]
        if breakout_day['Volume'] > mean_volume_50d * 1.5:
             return True, "Pattern detected with volume breakout"

    return False, "Pivot check failed"


# --- Main Screening Logic ---

def run_screening_and_charting(tickers):
    """
    Runs the full screening and charting process based on original requirements.
    """
    qualified_stocks = []

    print(f"Starting final screening for {len(tickers)} candidates from Finviz...")

    for symbol in tqdm(tickers, desc="Screening Stocks"):
        try:
            ticker = yf.Ticker(symbol)
            ticker_info = ticker.info

            if not ticker_info:
                logging.info(f"Skipping {symbol}: Insufficient basic info.")
                continue

            # Apply all original criteria
            price_ok, _ = check_price(ticker_info)
            if not price_ok: continue

            roe_ok, _ = check_roe(ticker_info)
            if not roe_ok: continue

            q_eps_ok, _ = check_quarterly_eps_growth(ticker)
            if not q_eps_ok: continue

            a_eps_ok, _ = check_annual_eps_growth(ticker)
            if not a_eps_ok: continue

            # New CWH check
            hist_df = ticker.history(period="2y") # Need more data for CWH
            if 'MA50' not in hist_df:
                hist_df['MA50'] = hist_df['Close'].rolling(window=50).mean()

            cwh_ok, reason = check_cup_with_handle(hist_df.copy())
            if not cwh_ok:
                logging.info(f"Skipping {symbol}: Did not pass CWH check. Reason: {reason}")
                continue

            # If all hard filters pass, this stock is qualified
            logging.info(f"QUALIFIED: {symbol}")
            qualified_stocks.append(symbol)

            # Generate chart for the qualified stock
            print(f"\nGenerating chart for qualified stock: {symbol}")
            generate_stock_chart(symbol)
            time.sleep(random.uniform(2, 4)) # Be polite

        except Exception as e:
            logging.error(f"Could not process {symbol}: {e}")
            continue

    return qualified_stocks

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Stock screener and chart generator.")
    parser.add_argument(
        '--file',
        type=str,
        default='tickers.csv',
        help="The path to the CSV file containing tickers, one per line."
    )
    args = parser.parse_args()

    # Load tickers from the CSV file generated by scrape_finviz.py
    try:
        ticker_list = pd.read_csv(args.file, header=None)[0].tolist()
    except FileNotFoundError:
        print(f"Error: Ticker file not found at '{args.file}'.")
        print("Please run scrape_finviz.py first to generate the candidate list.")
        exit()

    # Run the main screening and charting function
    final_results = run_screening_and_charting(ticker_list)

    if final_results:
        # Save the final list of qualified tickers
        results_df = pd.DataFrame(final_results, columns=['Ticker'])
        results_df.to_csv('screening_results.csv', index=False)
        print(f"\nScreening complete. Found {len(final_results)} qualified stocks.")
        print("Final list saved to screening_results.csv")
        print("Charts for these stocks have been generated.")
    else:
        print("\nScreening complete. No stocks met all the strict criteria.")
