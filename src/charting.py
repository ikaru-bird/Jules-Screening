import yfinance as yf
import pandas_ta as ta
import matplotlib.pyplot as plt
import matplotlib.font_manager
import sys
import os
import warnings

# Suppress known, harmless warnings from dependencies for a cleaner output
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, message="pkg_resources is deprecated")

def _get_jp_font():
    """Checks for common Japanese fonts and returns the name of the first one found."""
    jp_fonts = ['IPAexGothic', 'MS Gothic', 'Yu Gothic', 'Hiragino Sans', 'Osaka']
    available_fonts = [f.name for f in matplotlib.font_manager.fontManager.ttflist]

    for font in jp_fonts:
        if font in available_fonts:
            return font

    return None

def _plot_price_and_info(ax, hist, stock_data, financial_summary, status):
    """Plots the price chart and info box on the given axes."""
    # Use data passed from our input file
    symbol = stock_data['ticker']
    name = stock_data['name']
    sector = stock_data['sector']
    industry = stock_data['industry']

    title_status = f" - {status}" if status else ""
    ax.set_title(f"{symbol} - {name}{title_status}\nPrice, Volume, MACD")

    ax.plot(hist.index, hist['Close'], label='Close Price', color='blue')
    ax.set_ylabel("Price (USD)")
    ax.grid(True)

    # Display Company Name, Sector, and Industry in the info box
    info_text = (
        f"Company: {name}\n"
        f"Sector: {sector}\n"
        f"Industry: {industry}\n\n"
        f"{financial_summary.strip()}"
    )
    ax.text(0.01, 0.98, info_text, transform=ax.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.1))

def _plot_volume(ax, hist):
    """Plots the volume chart on the given axes."""
    ax.bar(hist.index, hist['Volume'], color='gray', alpha=0.7)
    ax.set_ylabel("Volume")
    ax.grid(True)

def _plot_macd(ax, hist):
    """Plots the MACD indicator on the given axes."""
    ax.plot(hist.index, hist['MACD_12_26_9'], label='MACD', color='green')
    ax.plot(hist.index, hist['MACDs_12_26_9'], label='Signal', color='red', linestyle='--')
    ax.bar(hist.index, hist['MACDh_12_26_9'], label='Histogram', color='purple', alpha=0.5)
    ax.set_ylabel("MACD")
    ax.legend()
    ax.grid(True)

def generate_stock_chart(stock_data, status=None):
    """
    Generates and saves a detailed stock chart for a given stock.
    The chart includes price, volume, MACD, and key financial info.
    An optional status can be provided to be included in the title and filename.
    """
    symbol = stock_data['ticker']
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", interval="1d")
        q_financials = ticker.quarterly_financials

        if hist.empty:
            print(f"Error: No historical data found for {symbol}", file=sys.stderr)
            return

        # Prepare financial data for display
        latest_revenue = ['N/A']*4
        if q_financials is not None and not q_financials.empty and 'Total Revenue' in q_financials.index:
            latest_revenue = q_financials.loc['Total Revenue'].iloc[:4].to_list()

        latest_eps = ['N/A']*4
        if q_financials is not None and not q_financials.empty and 'Basic EPS' in q_financials.index:
            latest_eps = q_financials.loc['Basic EPS'].iloc[:4].to_list()

        financial_summary = "Latest 4Q Results (Revenue | EPS):\n"
        for i in range(4):
            rev_str = f"${latest_revenue[i]/1e9:.2f}B" if isinstance(latest_revenue[i], (int, float)) else "N/A"
            eps_str = f"${latest_eps[i]:.2f}" if isinstance(latest_eps[i], (int, float)) else "N/A"
            q_num = i - 3
            financial_summary += f"Q{q_num: >2}: {rev_str} | {eps_str}\n"

        # Calculate technical indicators
        hist.ta.macd(append=True)

        # Create plot
        jp_font = _get_jp_font()
        if jp_font:
            plt.rcParams['font.family'] = jp_font
        else:
            print(f"Warning: No Japanese font found. Japanese characters may not render correctly.", file=sys.stderr)

        fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1.5]})

        # Pass the entire stock_data object to the plotting function
        _plot_price_and_info(axes[0], hist, stock_data, financial_summary, status)
        _plot_volume(axes[1], hist)
        _plot_macd(axes[2], hist)

        plt.xlabel("Date")
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        # Save figure
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        filename_status = f"_{status}" if status else ""
        filename = f"{symbol}{filename_status}.png"
        filepath = os.path.join(output_dir, filename)

        plt.savefig(filepath)
        plt.close(fig) # Close the figure to free memory
        print(f"Chart for {symbol} saved as {filepath}")

    except Exception as e:
        print(f"An error occurred while generating chart for {symbol}: {e}", file=sys.stderr)
