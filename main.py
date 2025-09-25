import argparse
import sys
import os

# Add the 'src' directory to the Python path
# This allows us to import modules from the src folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from data_fetcher import load_tickers_from_file
from screener import run_screening

def main():
    """
    Main function to orchestrate the screener application.
    Provides a command-line interface to run the screening process.
    """
    parser = argparse.ArgumentParser(
        description="A stock screening and charting tool based on O'Neil/Minervini principles.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Subparsers for commands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Screen command
    parser_screen = subparsers.add_parser(
        "screen",
        help="Runs the screening process on tickers found in the specified input file."
    )
    parser_screen.add_argument(
        "-i", "--input-file",
        required=False,
        default="_files/US/input.txt",
        help="Path to the input file containing tickers and company info. Defaults to _files/US/input.txt"
    )
    parser_screen.add_argument(
        "--top",
        type=int,
        default=None,
        help="Only screen the top N tickers from the input file."
    )

    args = parser.parse_args()

    if args.command == "screen":
        print("--- Executing Screen Command ---")
        print(f"Using input file: {args.input_file}")
        if args.top:
            print(f"Screening top {args.top} tickers.")

        ticker_list = load_tickers_from_file(args.input_file, num_tickers=args.top)

        if ticker_list is not None and not ticker_list.empty:
            run_screening(ticker_list)
        else:
            print("Could not proceed with screening. Ticker list is empty or file not found.")
        print("--- Screen Command Finished ---")

if __name__ == "__main__":
    # Ensure we are running from the project's root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    main()
