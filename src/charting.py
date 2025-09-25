import yfinance as yf
import pandas_ta as ta
import pandas as pd
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

def _plot_price_and_info(ax, hist, stock_data, status):
    """Plots the price chart and info box on the given axes."""
    symbol = stock_data['ticker']
    name = stock_data['name']
    sector = stock_data['sector']
    industry = stock_data['industry']

    # --- Build Financial Summary String ---
    info_text = ""

    # 1. Basic Info
    info_text += (
        f"Company: {name}\n"
        f"Sector: {sector}\n"
        f"Industry: {industry}\n\n"
    )

    # 2. Fundamental Analysis Results
    criteria_results = stock_data.get('criteria_results', [])
    passed_count = stock_data.get('criteria_passed_count', 0)
    if criteria_results:
        info_text += f"Fundamental Analysis ({passed_count}/4 Passed):\n"
        for name, is_ok, reason in criteria_results:
            name_short = name.replace("Annual", "A.").replace("Quarterly", "Q.")
            if reason == "--":
                status_icon = "-"
            elif is_ok:
                status_icon = "O"
            else:
                status_icon = "X"
            info_text += f" {status_icon} {name_short:<10}: {reason}\n"
        info_text += "\n"

    # 3. Recent Financials (Revenue/EPS) with Beat/Miss
    q_financials = stock_data.get('q_financials')
    earnings_dates = stock_data.get('earnings_dates')
    financial_summary = ""
    if q_financials is not None and not q_financials.empty:
        financial_summary += "Earnings | Revenue | EPS(vs Estimate):\n"
        if earnings_dates is not None and not earnings_dates.empty:
            earnings_dates.index = pd.to_datetime(earnings_dates.index).tz_localize(None)

        for i in range(min(4, len(q_financials.columns))):
            q_date = q_financials.columns[i]
            rev = q_financials.loc['Total Revenue'].iloc[i] if 'Total Revenue' in q_financials.index else None
            eps = q_financials.loc['Basic EPS'].iloc[i] if 'Basic EPS' in q_financials.index else None

            rev_str = f"${rev/1e9:.2f}B" if isinstance(rev, (int, float)) else "--"
            eps_str = f"${eps:.2f}" if isinstance(eps, (int, float)) else "--"

            eps_beat_miss_str = ""
            if eps is not None and earnings_dates is not None and not earnings_dates.empty:
                # DEBUG: Print dates to diagnose matching issues
                # print(f"--- Matching for {symbol} ---")
                # print(f"DEBUG: Quarter-end date from financials: {q_date}")

                # Widen the window to 45 days as report dates and announcement dates can differ significantly
                match = earnings_dates[
                    (earnings_dates.index > q_date) &
                    (earnings_dates.index < q_date + pd.Timedelta(days=60))
                ]

                # print(f"DEBUG: Available earnings_dates index: {earnings_dates.index}")
                # print(f"DEBUG: Found {len(match)} match(es) in window.")

                if not match.empty:
                    estimate_eps = match['EPS Estimate'].iloc[0]
                    if pd.notna(estimate_eps):
                        indicator = "O" if eps > estimate_eps else "X"
                        eps_beat_miss_str = f" (vs {estimate_eps:.2f}) {indicator}"

            q_date_str = q_date.strftime('%Y-%m')
            financial_summary += f" {q_date_str} | {rev_str} | {eps_str}{eps_beat_miss_str}\n"

    info_text += financial_summary.strip()

    # 4. Future Estimates
    info = stock_data.get('info', {})
    calendar = stock_data.get('calendar', {})
    estimates_summary = "\n\nGuidance | Revenue | EPS:\n"
    next_q_eps = calendar.get('Earnings Average', '--')
    next_q_rev = calendar.get('Revenue Average', '--')
    fwd_eps = info.get('forwardEps', '--')
    rev_growth = info.get('revenueGrowth', '--')

    eps_q_str = f"${next_q_eps:.2f}" if isinstance(next_q_eps, (int, float)) else "--"
    rev_q_str = f"${next_q_rev/1e9:.2f}B" if isinstance(next_q_rev, (int, float)) else "--"
    eps_y_str = f"${fwd_eps:.2f}" if isinstance(fwd_eps, (int, float)) else "--"
    rev_y_str = f"{rev_growth:.2%}" if isinstance(rev_growth, (int, float)) else "--"

    estimates_summary += f"  Next Q | {rev_q_str:<5} | {eps_q_str:<5}\n"
    estimates_summary += f"  Annual | {rev_y_str:<5} | {eps_y_str:<5}\n"
    info_text += estimates_summary

    # Plotting
    title_status = f" - {status}" if status else ""
    ax.set_title(f"{symbol} - {name}{title_status}\nPrice, Volume, MACD")
    ax.plot(hist.index, hist['Close'], label='Close Price', color='blue')
    ax.set_ylabel("Price (USD)")
    ax.grid(True)
    ax.text(0.01, 0.98, info_text, transform=ax.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.1),
             fontfamily='monospace')

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
    """
    symbol = stock_data['ticker']
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", interval="1d")

        if hist.empty:
            print(f"Error: No historical data found for {symbol}", file=sys.stderr)
            return

        hist.ta.macd(append=True)

        jp_font = _get_jp_font()
        if jp_font:
            plt.rcParams['font.family'] = jp_font
        else:
            print(f"Warning: No Japanese font found. Japanese characters may not render correctly.", file=sys.stderr)

        fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1.5]})

        # Add all data to the stock_data object to pass to the plotting function
        stock_data['q_financials'] = ticker.quarterly_financials
        stock_data['info'] = ticker.info
        stock_data['calendar'] = ticker.calendar
        try:
            stock_data['earnings_dates'] = ticker.earnings_dates
        except Exception:
            stock_data['earnings_dates'] = None

        _plot_price_and_info(axes[0], hist, stock_data, status)
        _plot_volume(axes[1], hist)
        _plot_macd(axes[2], hist)

        plt.xlabel("Date")
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        filename_status = f"_{status}" if status else ""
        filename = f"{symbol}{filename_status}.png"
        filepath = os.path.join(output_dir, filename)

        plt.savefig(filepath)
        plt.close(fig)
        print(f"Chart for {symbol} saved as {filepath}")

    except Exception as e:
        print(f"An error occurred while generating chart for {symbol}: {e}", file=sys.stderr)
