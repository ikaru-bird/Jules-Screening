import pandas as pd
from src import config

def load_tickers_from_file(filepath):
    """
    Loads tickers, company names, and industries from a tilde-separated file.

    Args:
        filepath (str): The path to the input file.

    Returns:
        pandas.DataFrame: A DataFrame with 'Ticker', 'Name', and 'Industry' columns,
                          or None if the file cannot be read.
    """
    try:
        # Read the file, using '~' as the separator.
        # The file has no header, so we specify that and name the first four columns.
        df = pd.read_csv(
            filepath,
            sep='~',
            header=None,
            usecols=[0, 1, 2, 3],
            names=['Ticker', 'Name', 'Sector', 'Industry']
        )
        print(f"Successfully loaded {len(df)} tickers from {filepath}")
        return df
    except FileNotFoundError:
        print(f"Error: Ticker file not found at '{filepath}'.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file {filepath}: {e}")
        return None
