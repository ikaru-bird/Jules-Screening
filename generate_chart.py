import yfinance as yf
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt
import argparse
import sys

def generate_stock_chart(symbol):
    """
    Generates and saves a detailed stock chart for a given symbol.
    """
    try:
        ticker = yf.Ticker(symbol)

        # --- 1. Fetch Data ---
        info = ticker.info
        hist = ticker.history(period="1y", interval="1d")
        q_financials = ticker.quarterly_financials
        q_earnings = ticker.quarterly_earnings

        if hist.empty:
            print(f"Error: No historical data found for {symbol}", file=sys.stderr)
            return

        # --- 2. Prepare Data ---
        # Company Info
        name = info.get('longName', 'N/A')
        sector = info.get('sector', 'N/A')

        # Financials
        latest_revenue = q_financials.loc['Total Revenue'].iloc[-4:].to_list() if 'Total Revenue' in q_financials.index else ['N/A']*4
        latest_eps = q_earnings['Earnings'].iloc[-4:].to_list() if not q_earnings.empty else ['N/A']*4

        # Format financial data for display
        financial_summary = "Latest 4Q Results (Revenue | EPS):\n"
        for i in range(4):
            rev_str = f"${latest_revenue[i]/1e9:.2f}B" if isinstance(latest_revenue[i], (int, float)) else "N/A"
            eps_str = f"${latest_eps[i]:.2f}" if isinstance(latest_eps[i], (int, float)) else "N/A"
            financial_summary += f"Q{i-4}: {rev_str} | {eps_str}\n"

        # Technical Indicators (MACD)
        hist.ta.macd(append=True)

        # --- 3. Create Plot ---
        # Attempt to use a Japanese-supporting font
        try:
            plt.rcParams['font.family'] = 'IPAexGothic'
            jp_font_found = True
        except:
            print("Warning: Japanese font not found. Using default font.", file=sys.stderr)
            jp_font_found = False

        fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1.5]})
        fig.suptitle(f"{symbol} - {name}", fontsize=20, y=0.98)

        # --- Panel 1: Price and Info ---
        ax1 = axes[0]
        ax1.plot(hist.index, hist['Close'], label='Close Price', color='blue')
        ax1.set_ylabel("Price (USD)")
        ax1.set_title("Price, Volume, MACD")
        ax1.grid(True)

        # Add text info box
        info_text = f"{'セクター' if jp_font_found else 'Sector'}: {sector}\n\n{financial_summary.strip()}"
        ax1.text(0.01, 0.98, info_text, transform=ax1.transAxes, fontsize=10,
                 verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.1))

        # --- Panel 2: Volume ---
        ax2 = axes[1]
        ax2.bar(hist.index, hist['Volume'], color='gray', alpha=0.7)
        ax2.set_ylabel("Volume")
        ax2.grid(True)

        # --- Panel 3: MACD ---
        ax3 = axes[2]
        ax3.plot(hist.index, hist['MACD_12_26_9'], label='MACD', color='green')
        ax3.plot(hist.index, hist['MACDs_12_26_9'], label='Signal', color='red', linestyle='--')
        ax3.bar(hist.index, hist['MACDh_12_26_9'], label='Histogram', color='purple', alpha=0.5)
        ax3.set_ylabel("MACD")
        ax3.legend()
        ax3.grid(True)

        plt.xlabel("Date")
        fig.tight_layout(rect=[0, 0, 1, 0.96]) # Adjust layout to make room for suptitle

        # --- 4. Save Figure ---
        filename = f"{symbol}.png"
        plt.savefig(filename)
        print(f"Chart for {symbol} saved as {filename}")

    except Exception as e:
        print(f"An error occurred while generating chart for {symbol}: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a stock chart for a given ticker symbol.")
    parser.add_argument("symbol", type=str, help="The stock ticker symbol (e.g., 'AAPL').")
    args = parser.parse_args()

    generate_stock_chart(args.symbol.upper())
