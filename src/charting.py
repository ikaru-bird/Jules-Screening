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
import numpy as np
from src import config

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

def _draw_pivot_line(ax, pivot_price, pivot_date, hist_df):
    """Draws the pivot line on the price chart from the pivot date onwards."""
    if pivot_date is None or pivot_date not in hist_df.index:
        return

    # Get the date range from the pivot date to the last date in the history
    line_dates = hist_df.loc[pivot_date:].index
    # Create an array of the pivot price with the same length as the date range
    line_values = [pivot_price] * len(line_dates)

    # Plot a line segment
    ax.plot(line_dates, line_values, color='red', linestyle='--', linewidth=1.2, label=f'Pivot: {pivot_price:.2f}')

def _draw_cwh_pattern(ax, points, hist_df):
    """Draws the Cup with Handle pattern outline."""
    # Extract points, ignoring any that are None
    cup_points = [p for p in [points.get('cup_left_lip'), points.get('cup_bottom'), points.get('cup_right_lip')] if p]
    handle_low = points.get('handle_low')
    cup_right_lip = points.get('cup_right_lip')

    # Draw the cup arc if we have all three points
    if len(cup_points) == 3:
        dates = [p[0] for p in cup_points]
        prices = [p[1] for p in cup_points]

        # Convert dates to numerical values for polynomial fitting
        date_nums = mdates.date2num(dates)

        # Fit a 2nd degree polynomial (parabola) to the three points
        coeffs = np.polyfit(date_nums, prices, 2)
        poly = np.poly1d(coeffs)

        # Generate smooth x-values (dates) between the left and right lip for the curve
        arc_date_nums = np.linspace(date_nums[0], date_nums[2], 100)
        arc_dates = mdates.num2date(arc_date_nums)
        arc_prices = poly(arc_date_nums)

        ax.plot(arc_dates, arc_prices, color='blue', linestyle='--', linewidth=1)

    # Draw the handle
    if handle_low and cup_right_lip:
        handle_dates = [cup_right_lip[0], handle_low[0]]
        handle_prices = [cup_right_lip[1], handle_low[1]]
        ax.plot(handle_dates, handle_prices, color='blue', linestyle='--', linewidth=1)

    # If a breakout has occurred, draw a line from the handle low to the breakout point
    breakout_point = points.get('breakout_point')
    if handle_low and breakout_point:
        breakout_line_dates = [handle_low[0], breakout_point[0]]
        breakout_line_prices = [handle_low[1], breakout_point[1]]
        ax.plot(breakout_line_dates, breakout_line_prices, color='blue', linestyle='--', linewidth=1)

def _draw_db_pattern(ax, points, hist_df):
    """Draws the Double Bottom (W-shape) pattern outline."""
    first_trough = points.get('first_trough')
    peak = points.get('peak')
    second_trough = points.get('second_trough')
    breakout_point = points.get('breakout_point') # Get the breakout point

    if not all([first_trough, peak, second_trough]):
        return # Not enough points to draw the basic W

    # Find a suitable starting point for the "W"
    start_search_end = first_trough[0] - pd.Timedelta(days=5)
    start_search_start = first_trough[0] - pd.Timedelta(days=60)
    entry_df = hist_df.loc[start_search_start:start_search_end]
    if entry_df.empty:
        # If no data before the first trough, start the line from the first trough itself
        start_point_date = first_trough[0]
        start_point_price = first_trough[1]
    else:
        start_point_date = entry_df['High'].idxmax()
        start_point_price = entry_df['High'].max()

    # Assemble the points of the "W"
    w_dates = [start_point_date, first_trough[0], peak[0], second_trough[0]]
    w_prices = [start_point_price, first_trough[1], peak[1], second_trough[1]]

    # If a breakout has occurred, extend the line to the breakout point
    if breakout_point:
        w_dates.append(breakout_point[0])
        w_prices.append(breakout_point[1])

    ax.plot(w_dates, w_prices, color='blue', linestyle='--', linewidth=1)

def _draw_vcp_pattern(ax, points, hist_df):
    """Draws the Volatility Contraction Pattern outline."""
    if not points or len(points) < 2:
        return

    vcp_dates = [p[1] for p in points]
    vcp_prices = [p[2] for p in points]

    ax.plot(vcp_dates, vcp_prices, color='blue', linestyle='--', linewidth=1, marker='o', markersize=3)


def generate_stock_chart(stock_data, status=None, pattern_data=None, output_dir="Output"):
    """
    Generates and saves a detailed stock chart using a manual matplotlib layout
    and mplfinance for plotting. This provides maximum control over the final output.
    """
    symbol = stock_data['ticker']
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2y", interval="1d")
        if hist.empty:
            print(f"Error: No historical data found for {symbol}", file=sys.stderr)
            return
        # Align timezone-awareness with the data used for pattern detection
        hist.index = hist.index.tz_localize(None)

        hist.ta.macd(append=True)

        jp_font = _get_jp_font()
        font_props = {'family': jp_font} if jp_font else {}
        if jp_font: plt.rcParams['font.family'] = jp_font

        # --- 1. Manually Create Figure and Axes ---
        fig = plt.figure(figsize=(16, 9))
        gs = gridspec.GridSpec(3, 1, height_ratios=[4.5, 1, 1.5])

        ax_price = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharex=ax_price)
        ax_macd = fig.add_subplot(gs[2], sharex=ax_price)

        plt.setp(ax_price.get_xticklabels(), visible=False)
        plt.setp(ax_vol.get_xticklabels(), visible=False)

        # --- 2. Plot data onto the pre-configured axes ---
        s = mpf.make_mpf_style(base_mpf_style='yahoo', gridstyle='-')
        mpf.plot(hist, type='candle', ax=ax_price, style=s, show_nontrading=True)

        # Manually plot Volume to match candle colors
        price_colors = ['#26a69a' if c >= o else '#ef5350' for o, c in zip(hist['Open'], hist['Close'])]
        ax_vol.bar(hist.index, hist['Volume'], color=price_colors, width=0.8, align='center')

        # Manually plot MACD and color histogram to match candle colors
        macd_hist = hist['MACDh_12_26_9']
        ax_macd.bar(hist.index, macd_hist, color=price_colors, width=0.7, label='Histogram')
        ax_macd.plot(hist.index, hist['MACD_12_26_9'], color='green', label='MACD')
        ax_macd.plot(hist.index, hist['MACDs_12_26_9'], color='red', linestyle='--', label='Signal')
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
                      verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', fc='#f0f0f0', alpha=0.8),
                      fontfamily='monospace')

        for ax in [ax_price, ax_vol, ax_macd]:
            ax.grid(True, linestyle='--', alpha=0.6)

        # --- 5. Draw Pattern and Pivot Line ---
        if pattern_data:
            pivot = pattern_data.get('pivot')
            pivot_date = pattern_data.get('pivot_date')
            points = pattern_data.get('points')
            pattern_type = pattern_data.get('type')

            if pivot and pivot_date:
                _draw_pivot_line(ax_price, pivot, pivot_date, hist)

            if points:
                if pattern_type == 'CWH':
                    _draw_cwh_pattern(ax_price, points, hist)
                elif pattern_type == 'DB':
                    _draw_db_pattern(ax_price, points, hist)
                elif pattern_type == 'VCP':
                    _draw_vcp_pattern(ax_price, points, hist)

            # --- Draw Power Play Indicators ---
            if 'sma_short' in pattern_data and 'sma_long' in pattern_data:
                # Reindex indicator data to match the main chart's date range to prevent dimension mismatch
                sma_short = pattern_data['sma_short'].reindex(hist.index)
                sma_long = pattern_data['sma_long'].reindex(hist.index)
                ax_price.plot(hist.index, sma_short, color='orange', linestyle='-', linewidth=1, label=f'SMA {config.PP_TREND_SMA_SHORT}')
                ax_price.plot(hist.index, sma_long, color='purple', linestyle='-', linewidth=1, label=f'SMA {config.PP_TREND_SMA_LONG}')

            if 'bbands' in pattern_data:
                bb = pattern_data['bbands']
                # Reindex each band to the main chart's date range
                bb_upper = bb['upper'].reindex(hist.index)
                bb_lower = bb['lower'].reindex(hist.index)
                ax_price.plot(hist.index, bb_upper, color='cyan', linestyle='--', linewidth=0.7, label='BBands Upper')
                ax_price.plot(hist.index, bb_lower, color='cyan', linestyle='--', linewidth=0.7)
                ax_price.fill_between(hist.index, bb_lower, bb_upper, color='cyan', alpha=0.1)

            # --- 5a. Consolidate and draw legend ---
            # Only draw legend if there are items with labels to display
            handles, labels = ax_price.get_legend_handles_labels()
            if handles:
                ax_price.legend()


        # --- 6. Save Figure ---
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