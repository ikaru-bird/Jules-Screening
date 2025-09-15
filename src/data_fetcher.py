import requests
from bs4 import BeautifulSoup
import time
import random
import yfinance as yf
import pandas as pd

from src import config

def scrape_finviz_tickers():
    """
    Scrapes tickers from Finviz.com based on the URL in the config.
    Handles pagination and saves the result to a CSV file.
    """
    tickers = []
    page = 1

    print("Starting Finviz scrape...")
    while True:
        # Finviz pagination is done by adding '&r=' where r is the starting rank
        url = f"{config.FINVIZ_URL}&r={(page-1)*20 + 1}"
        print(f"Scraping page {page}: {url}")

        try:
            response = requests.get(url, headers=config.SCRAPER_HEADERS)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            results_table = soup.find('table', class_='screener_table')
            if not results_table:
                print("Could not find results table. Ending scrape.")
                break

            rows = results_table.find_all('tr', valign='top')
            page_tickers = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 1:
                    ticker_link = cols[1].find('a')
                    if ticker_link:
                        page_tickers.append(ticker_link.get_text())

            if not page_tickers:
                print("No more tickers found on this page. Ending scrape.")
                break

            tickers.extend(page_tickers)

            page += 1
            time.sleep(random.uniform(1, 3))

        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            break

    unique_tickers = sorted(list(set(tickers)))

    if unique_tickers:
        # Overwrite the file with the new, high-quality list
        with open(config.TICKERS_FILE, 'w') as f:
            for ticker in unique_tickers:
                f.write(f"{ticker}\n")
        print(f"\nScraping complete. Found {len(unique_tickers)} tickers.")
        print(f"Results saved to {config.TICKERS_FILE}")
    else:
        print("\nScraping complete. No tickers were found for the given criteria.")

    return unique_tickers

def load_tickers_from_file():
    """Loads a list of tickers from the configured file."""
    try:
        return pd.read_csv(config.TICKERS_FILE, header=None)[0].tolist()
    except FileNotFoundError:
        print(f"Error: Ticker file not found at '{config.TICKERS_FILE}'.")
        print("Please run the 'scrape' command first to generate the candidate list.")
        return None
