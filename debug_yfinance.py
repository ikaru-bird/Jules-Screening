import yfinance as yf
import pprint

tickers_to_test = ['AAPL', 'MSFT', 'GOOG', 'META']

print("--- Starting yfinance diagnostic test ---")

for symbol in tickers_to_test:
    print(f"\n--- Processing: {symbol} ---")
    try:
        ticker = yf.Ticker(symbol)

        # The .info dictionary is where the fundamental data lives.
        # If this call fails or returns an empty dict, that's the root cause.
        info_dict = ticker.info

        if not info_dict:
            print(f"Result for {symbol}: FAILED - .info dictionary is empty.")
            continue

        print(f"Result for {symbol}: SUCCESS")

        # Print specific keys we need for the screener
        print(f"  - ROE (returnOnEquity): {info_dict.get('returnOnEquity')}")
        print(f"  - Sector (sector): {info_dict.get('sector')}")

        # Disclose all results as requested
        print(f"  - Full .info dictionary for {symbol}:")
        pprint.pprint(info_dict)

    except Exception as e:
        print(f"Result for {symbol}: FAILED - An exception occurred.")
        print(f"  - Exception details: {e}")

print("\n--- yfinance diagnostic test complete ---")
