import yfinance as yf
import pandas_ta as ta
import pandas as pd
import mplfinance as mpf
import matplotlib.font_manager
import sys
import os
import warnings
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates

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

def _build_info_text(stock_data):
    """
    Builds the text for the information box.
    This version specifically excludes the Company, Sector, and Industry lines.
    """
    info_text = ""

    # 1. Fundamental Analysis Results
    criteria_results = stock_data.get('criteria_results', [])
    passed_count = stock_data.get('criteria_passed_count', 0)
    if criteria_results:
        total_criteria = len(criteria_results)
        info_text += f"Fundamental Analysis ({passed_count}/{total_criteria} Passed):\n"
        for name, is_ok, reason in criteria_results:
            status_icon = "-" if reason == "--" else "O" if is_ok else "X"
            info_text += f" {status_icon} {name:<22}: {reason}\n"
        info_text += "\n"

    # 2. Recent Financials (Revenue/EPS) with Beat/Miss
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
                match = earnings_dates[
                    (earnings_dates.index > q_date) & (earnings_dates.index < q_date + pd.Timedelta(days=60))
                ]
                if not match.empty:
                    estimate_eps = match['EPS Estimate'].iloc[0]
                    if pd.notna(estimate_eps):
                        indicator = "O" if eps > estimate_eps else "X"
                        eps_beat_miss_str = f" (vs {estimate_eps:.2f}) {indicator}"
            q_date_str = q_date.strftime('%Y-%m')
            financial_summary += f" {q_date_str} | {rev_str} | {eps_str}{eps_beat_miss_str}\n"
    info_text += financial_summary.strip()

    # 3. Future Estimates
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

    return info_text

def generate_stock_chart(stock_data, status=None):
    """
    Generates and saves a detailed stock chart using a manual matplotlib layout
    and mplfinance for plotting. This provides maximum control over the final output.
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
        font_props = {'family': jp_font} if jp_font else {}
        if jp_font: plt.rcParams['font.family'] = jp_font

        # --- 1. Manually Create Figure and Axes ---
        fig = plt.figure(figsize=(16, 9))
        gs = gridspec.GridSpec(3, 1, height_ratios=[3, 1, 1.5])

        ax_price = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharex=ax_price)
        ax_macd = fig.add_subplot(gs[2], sharex=ax_price)

        plt.setp(ax_price.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)

        # --- 2. Plot data onto the pre-configured axes ---
        s = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle='-')
        # Plot price data only, volume will be plotted manually
        mpf.plot(hist, type='candle', ax=ax_price, style=s, show_nontrading=True)

        # Manually plot Volume
        colors = ['g' if c >= o else 'r' for o, c in zip(hist['Open'], hist['Close'])]
        ax_vol.bar(hist.index, hist['Volume'], color=colors, width=0.8, align='center')

        # Manually plot MACD
        ax_macd.plot(hist.index, hist['MACD_12_26_9'], color='green', label='MACD')
        ax_macd.plot(hist.index, hist['MACDs_12_26_9'], color='red', linestyle='--', label='Signal')
        ax_macd.bar(hist.index, hist['MACDh_12_26_9'], color='purple', alpha=0.5, width=0.7, label='Histogram')
        ax_macd.legend()

        # --- 3. Configure Layout, Titles, and Margins ---
        name = stock_data['name']
        sector = stock_data.get('sector', 'N/A')
        industry = stock_data.get('industry', 'N/A')

        main_title = f"{symbol}, {name}"
        subtitle = f"Sector: {sector} :: Industry: {industry}"

        fig.text(0.5, 0.97, main_title, ha='center', va='center', fontsize=16, **font_props)
        fig.text(0.5, 0.93, subtitle, ha='center', va='center', fontsize=12, **font_props)

        fig.subplots_adjust(left=0.04, right=0.95, top=0.90, bottom=0.07)

        # --- 4. Configure Axes (Labels, Ticks, Info Box, Grid) ---
        ax_price.set_ylabel("Price (USD)")
        ax_vol.set_ylabel("Volume")
        ax_macd.set_ylabel("MACD")

        # Move Volume and MACD Y-axis to the right
        ax_vol.yaxis.tick_right()
        ax_vol.yaxis.set_label_position("right")
        ax_macd.yaxis.tick_right()
        ax_macd.yaxis.set_label_position("right")

        ax_macd.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax_macd.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        fig.autofmt_xdate(rotation=0, ha='center')

        stock_data['q_financials'] = ticker.quarterly_financials
        stock_data['info'] = ticker.info
        stock_data['calendar'] = ticker.calendar
        try:
            stock_data['earnings_dates'] = ticker.earnings_dates
        except Exception:
            stock_data['earnings_dates'] = None

        info_text = _build_info_text(stock_data)
        ax_price.text(0.015, 0.98, info_text, transform=ax_price.transAxes, fontsize=9,
                      verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.4),
                      fontfamily='monospace')

        for ax in [ax_price, ax_vol, ax_macd]:
            ax.grid(True, linestyle='--', alpha=0.6)

        # --- 5. Save Figure ---
        output_dir = "Output"
        os.makedirs(output_dir, exist_ok=True)
        filename_status = f"_{status}" if status else ""
        filename = f"{symbol}{filename_status}.png"
        filepath = os.path.join(output_dir, filename)

        plt.savefig(filepath)
        plt.close(fig)
        print(f"Chart for {symbol} saved as {filepath}")

    except Exception as e:
        print(f"An error occurred while generating chart for {symbol}: {e}", file=sys.stderr)
        if 'fig' in locals() and plt.fignum_exists(fig.number):
            plt.close(fig)