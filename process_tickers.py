import pandas as pd

# Load NASDAQ-listed stocks
nasdaq_df = pd.read_csv('nasdaqlisted.txt', delimiter='|')
# Filter out test issues and non-common stocks (e.g., warrants, units)
nasdaq_df = nasdaq_df[(nasdaq_df['Test Issue'] == 'N')]
nasdaq_tickers = nasdaq_df['Symbol'].dropna()

# Load other listed stocks (e.g., NYSE, AMEX)
other_df = pd.read_csv('otherlisted.txt', delimiter='|')
# The ticker symbol is in the 'ACT Symbol' column
# Filter out test issues and non-common stocks
other_df = other_df[(other_df['Test Issue'] == 'N')]
other_tickers = other_df['ACT Symbol'].dropna()

# Combine the ticker lists
all_tickers = pd.concat([nasdaq_tickers, other_tickers], ignore_index=True)

# Clean up tickers: yfinance usually works best with simple, uppercase tickers.
# This will filter out many warrants, preferred shares, etc. (e.g., 'BRK.B', 'BF.B' will be kept, but 'Warrant.W' will be removed)
# A more robust filter might be needed, but this is a good start.
all_tickers = all_tickers[all_tickers.str.match(r'^[A-Z.]+$')]
all_tickers = all_tickers[~all_tickers.str.contains(r'\$')]


# Remove duplicates
all_tickers = all_tickers.drop_duplicates()

# Save to a CSV file, without header and index
all_tickers.to_csv('tickers.csv', index=False, header=False)

print(f"Processed and saved {len(all_tickers)} tickers to tickers.csv")
