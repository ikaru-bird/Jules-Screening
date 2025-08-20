import requests
from bs4 import BeautifulSoup
import time
import random

def get_tickers_from_finviz():
    """
    Scrapes tickers from Finviz.com using the user-provided URL.
    Handles pagination and uses a robust selector for the given view.
    """
    # Use the exact URL provided by the user.
    base_url = "https://finviz.com/screener.ashx?v=152&f=fa_epsqoq_o10,fa_epsyoy_o10,ind_stocksonly,sh_price_o10&ft=2&o=-marketcap&c=0,1,2,3,4,6,7,8,65,67,68"

    tickers = []
    page = 1

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    while True:
        # Finviz pagination is done by adding '&r=' where r is the starting rank
        url = f"{base_url}&r={(page-1)*20 + 1}"
        print(f"Scraping page {page}: {url}")

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Robust selector for the v=152 view. Find links inside the results table
            # whose href starts with 'quote.ashx?t='. The second link in each row is the ticker.
            # A simpler approach is to find all such links and rely on the text content.
            results_table = soup.find('table', class_='screener_table')
            if not results_table:
                print("Could not find results table. Ending scrape.")
                break

            # This selector finds all links within the results table that point to a quote page.
            # It's more specific and robust than just using a class name.
            # We take the text of these links, which is the ticker symbol.
            ticker_links = results_table.select('a.screener-link-primary, a.tab-link[href^="quote.ashx?t="]')

            # The above selector might grab company names too. A more precise way for this view:
            # Find all rows, then find the second 'a' tag in each.
            # But let's try a simpler text-based extraction first, then refine if needed.
            # The ticker is always inside an 'a' tag.

            # Let's find all the table rows and extract the ticker from the second column
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

    return sorted(list(set(tickers)))

if __name__ == "__main__":
    print("Starting Finviz scrape with user-provided URL...")
    scraped_tickers = get_tickers_from_finviz()

    if scraped_tickers:
        # Overwrite the file with the new, high-quality list
        with open('tickers.csv', 'w') as f:
            for ticker in scraped_tickers:
                f.write(f"{ticker}\n")
        print(f"\nScraping complete. Found {len(scraped_tickers)} tickers.")
        print("Results saved to tickers.csv")
    else:
        print("\nScraping complete. No tickers were found for the given criteria.")
