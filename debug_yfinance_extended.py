import yfinance as yf
import pprint
import pandas as pd

# Set pandas to display all rows/columns to avoid truncation in the output
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

ticker_symbol = 'MSFT'
print(f"--- Starting detailed yfinance data analysis for {ticker_symbol} ---")

ticker = yf.Ticker(ticker_symbol)

def print_section(title, data):
    print(f"\n{'='*20} {title} {'='*20}")
    if isinstance(data, dict):
        pprint.pprint(data)
    elif isinstance(data, pd.DataFrame):
        if data.empty:
            print("DataFrame is empty.")
        else:
            print(data)
    elif data is None:
        print("Data is None.")
    else:
        print(data)

# 1. ticker.info (Dictionary)
# Contains summary data, including trailing/forward EPS and outstanding shares
try:
    print_section("ticker.info", ticker.info)
except Exception as e:
    print_section("ticker.info", f"Error fetching .info: {e}")

# 2. Annual Financials (DataFrame)
# Main income statement. Should contain 'Basic EPS'.
try:
    print_section("ticker.financials (Annual Income Statement)", ticker.financials)
except Exception as e:
    print_section("ticker.financials", f"Error fetching .financials: {e}")

# 3. Quarterly Financials (DataFrame)
# Quarterly income statement.
try:
    print_section("ticker.quarterly_financials (Quarterly Income Statement)", ticker.quarterly_financials)
except Exception as e:
    print_section("ticker.quarterly_financials", f"Error fetching .quarterly_financials: {e}")

# 4. Annual Balance Sheet (DataFrame)
try:
    print_section("ticker.balance_sheet (Annual)", ticker.balance_sheet)
except Exception as e:
    print_section("ticker.balance_sheet", f"Error fetching .balance_sheet: {e}")

# 5. Quarterly Balance Sheet (DataFrame)
try:
    print_section("ticker.quarterly_balance_sheet (Quarterly)", ticker.quarterly_balance_sheet)
except Exception as e:
    print_section("ticker.quarterly_balance_sheet", f"Error fetching .quarterly_balance_sheet: {e}")

# 6. Annual Cash Flow (DataFrame)
try:
    print_section("ticker.cashflow (Annual)", ticker.cashflow)
except Exception as e:
    print_section("ticker.cashflow", f"Error fetching .cashflow: {e}")

# 7. Quarterly Cash Flow (DataFrame)
try:
    print_section("ticker.quarterly_cashflow (Quarterly)", ticker.quarterly_cashflow)
except Exception as e:
    print_section("ticker.quarterly_cashflow", f"Error fetching .quarterly_cashflow: {e}")

# 8. Annual Earnings (DataFrame) - Often less detailed
try:
    print_section("ticker.earnings (Annual)", ticker.earnings)
except Exception as e:
    print_section("ticker.earnings", f"Error fetching .earnings: {e}")

# 9. Quarterly Earnings (DataFrame) - This is what the original script uses
try:
    print_section("ticker.quarterly_earnings (Quarterly)", ticker.quarterly_earnings)
except Exception as e:
    print_section("ticker.quarterly_earnings", f"Error fetching .quarterly_earnings: {e}")


print(f"\n--- Analysis for {ticker_symbol} complete ---")
