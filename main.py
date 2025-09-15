import argparse
import sys
import os

# Add the 'src' directory to the Python path
# This allows us to import modules from the src folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from data_fetcher import scrape_finviz_tickers, load_tickers_from_file
from screener import run_screening

def main():
    """
    Main function to orchestrate the screener application.
    Provides a command-line interface to run different stages of the process.
    """
    parser = argparse.ArgumentParser(
        description="A stock screening and charting tool based on O'Neil/Minervini principles.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "command",
        choices=["scrape", "screen"],
        help=(
            "The command to execute:\n"
            "  scrape - Fetches a new list of candidate tickers from Finviz.com and saves to tickers.csv.\n"
            "  screen - Runs the screening process on tickers found in tickers.csv."
        )
    )
    args = parser.parse_args()

    if args.command == "scrape":
        print("--- Executing Scrape Command ---")
        scrape_finviz_tickers()
        print("--- Scrape Command Finished ---")

    elif args.command == "screen":
        print("--- Executing Screen Command ---")
        ticker_list = load_tickers_from_file()
        if ticker_list:
            run_screening(ticker_list)
        else:
            print("Could not proceed with screening. Ticker list is empty or file not found.")
        print("--- Screen Command Finished ---")

if __name__ == "__main__":
    # Ensure we are running from the project's root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    main()
