import argparse
import pandas as pd
import sys
import os

# Ensure the src directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.screener import run_screening
from src import config

def main():
    """
    Main function to run the stock screener.
    Parses command-line arguments for input file and screening limits.
    """
    parser = argparse.ArgumentParser(description="Stock Screener based on financial criteria and chart patterns.")

    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    # --- Screen Command ---
    screen_parser = subparsers.add_parser('screen', help='Run the screening process.')
    screen_parser.add_argument(
        '-i', '--input-file',
        type=str,
        default=config.DEFAULT_INPUT_FILE,
        help=f"Path to the input file containing tickers. Defaults to {config.DEFAULT_INPUT_FILE}"
    )
    screen_parser.add_argument(
        '--top',
        type=int,
        default=None,
        help="Screen only the top N stocks from the input file."
    )

    args = parser.parse_args()

    if args.command == 'screen':
        # Check if the input file exists
        if not os.path.exists(args.input_file):
            print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
            sys.exit(1)

        print(f"Loading tickers from {args.input_file}...")

        # Load the tickers, specifying the separator and column names
        try:
            # The file has more columns than needed; only parse the first four.
            ticker_df = pd.read_csv(
                args.input_file,
                sep='~',
                header=None,
                names=['Ticker', 'Name', 'Sector', 'Industry', 'Extra1', 'Extra2', 'Extra3', 'Extra4', 'Extra5', 'Extra6'],
                usecols=['Ticker', 'Name', 'Sector', 'Industry']
            )
        except Exception as e:
            print(f"Error reading or parsing the input file: {e}", file=sys.stderr)
            sys.exit(1)

        # Limit the number of stocks if --top is specified
        if args.top is not None:
            print(f"Screening the top {args.top} tickers.")
            ticker_df = ticker_df.head(args.top)

        # Run the main screening logic
        run_screening(ticker_df)

if __name__ == "__main__":
    main()