import pandas as pd
from tqdm import tqdm
import logging
import time
from generate_chart import generate_stock_chart
import argparse

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='screener.log')

def run_chart_generation(tickers):
    """
    Reads a list of tickers and generates a chart for each one.
    """
    if not tickers:
        print("Ticker list is empty. No charts to generate.")
        return

    print(f"Starting chart generation for {len(tickers)} tickers...")

    for symbol in tqdm(tickers, desc="Generating Charts"):
        print(f"\nGenerating chart for: {symbol}")
        try:
            generate_stock_chart(symbol)
            # Be polite to the API server to avoid rate-limiting
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            logging.error(f"Could not generate chart for {symbol}: {e}")
            print(f"Failed to generate chart for {symbol}. See screener.log for details.")
            continue

if __name__ == '__main__':
    import random

    parser = argparse.ArgumentParser(description="Chart generator for a list of tickers.")
    parser.add_argument(
        '--file',
        type=str,
        default='tickers.csv',
        help="The path to the CSV file containing tickers, one per line."
    )
    args = parser.parse_args()

    # Load tickers from the CSV file
    try:
        ticker_list = pd.read_csv(args.file, header=None)[0].tolist()
    except FileNotFoundError:
        print(f"Error: Ticker file not found at '{args.file}'.")
        print("Please run scrape_finviz.py first to generate tickers.csv.")
        exit()

    # Run the main chart generation function
    run_chart_generation(ticker_list)

    print("\nChart generation complete.")
