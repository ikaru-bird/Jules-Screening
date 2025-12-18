"""
Configuration file for the stock screener application.

This file centralizes all the settings, thresholds, and parameters
used throughout the application, making it easy to adjust the behavior
of the scraper, financial checks, and pattern recognition logic.
"""

# -- General Settings --
DEFAULT_INPUT_FILE = '_files/US/input.txt'
TICKERS_FILE = 'tickers.csv'
RESULTS_FILE = 'screening_results.csv'
LOG_FILE = 'screener.log'

# -- Finviz Scraper Settings --
# URL for stocks with >10% quarterly and annual EPS growth, priced >$10
FINVIZ_URL = "https://finviz.com/screener.ashx?v=152&f=fa_epsqoq_o10,fa_epsyoy_o10,ind_stocksonly,sh_price_o10&ft=2&o=-marketcap&c=0,1,2,3,4,6,7,8,65,67,68"
SCRAPER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# -- Financial Screening Criteria (O'Neil / Minervini) --
# Using 'Standard Growth' profile. 'Strict Growth' values are commented out for reference.
MIN_PRICE = 10.00
MIN_ROE = 0.12 # Strict: 0.15
MIN_Q_EPS_GROWTH = 0.15 # Strict: 0.25
MIN_ANNUAL_EPS_GROWTH_CAGR = 0.15 # Strict: 0.25
MIN_ANNUAL_EPS_YOY_GROWTH = 0.15 # Strict: 0.25

# -- Cup With Handle (CWH) Pattern Parameters (REVISED) --
CWH_LOOKBACK_PERIOD = "2y" # Data period to fetch for pattern analysis

# Prior Uptrend parameters
UPTREND_LOOKBACK_DAYS = 90 # Look back 3 months for a prior uptrend
UPTREND_MIN_RISE_FACTOR = 1.3 # Must have risen at least 30%

# Cup parameters
# Using 'Standard' profile. 'Strict' value is commented out.
CUP_MIN_DEPTH_FACTOR = 1.25 # The peak must be >= 25% higher than the bottom. Strict: 1.3
CUP_MIN_DURATION_DAYS = 49  # 7 weeks
CUP_MAX_DURATION_DAYS = 455 # 65 weeks
# The two lips of the cup should be close in price
CUP_LIP_MAX_DEVIATION = 1.10 # Right lip can be max 10% higher than left
CUP_LIP_MIN_DEVIATION = 0.90 # Right lip can be min 10% lower than left
# To ensure a "U" shape, not a "V"
CUP_MIN_ROUNDED_POINTS = 5 # At least 5 days must be near the cup's low point

# Handle parameters
HANDLE_MAX_DURATION_DAYS = 35 # 7 weeks
HANDLE_MIN_DURATION_DAYS = 5   # 1 week
# Defines the allowable pullback of the handle relative to the cup's high.
# e.g., MIN=0.85 allows a pullback of up to 15%.
HANDLE_DEPTH_MIN_FACTOR = 0.85 # Max pullback depth
HANDLE_DEPTH_MAX_FACTOR = 1.00 # Handle shouldn't be higher than the cup's high

# Pivot (breakout) parameters
PIVOT_LOOKAHEAD_DAYS = 180   # How many days to look for a pivot breakout after the handle
VOLUME_BREAKOUT_FACTOR = 1.5 # Volume on breakout day must be 1.5x the 50-day average

# -- Double Bottom (DB) Pattern Parameters --
DB_LOOKBACK_PERIOD = "1y"

# Prior Downtrend parameters
DB_DOWNTREND_LOOKBACK_DAYS = 120 # Look back 4 months for a prior downtrend
DB_DOWNTREND_MIN_DROP_FACTOR = 1.3 # Must have dropped at least 30%

# W-Shape parameters
DB_DURATION_MIN_DAYS = 42 # 6 weeks
DB_DURATION_MAX_DAYS = 270 # ~9 months
DB_TROUGH_MAX_DEVIATION = 1.05 # Second trough can be max 5% different from the first
DB_PEAK_MIN_RISE_FACTOR = 1.10 # The peak between troughs must be at least 10% higher than the first trough
DB_MIN_ROUNDED_POINTS = 3 # To ensure troughs are not too sharp (V-shaped)
DB_PIVOT_PROXIMITY_FACTOR = 0.97 # Price must be within 3% of the pivot to be considered "consolidating"
DB_VOLUME_DROP_FACTOR = 0.8 # Average volume on 2nd trough should be less than the 1st

# -- Volatility Contraction Pattern (VCP) Parameters --
VCP_LOOKBACK_PERIOD = "1y"

# Defines the expected percentage contraction for each stage.
# e.g., 1st contraction ~25%, 2nd ~15%, 3rd ~8%
VCP_CONTRACTIONS = [0.25, 0.15, 0.08]
VCP_CONTRACTION_MAX_DEVIATION = 1.5 # Allowable deviation from the expected contraction depth (e.g., 1.5 means 50% deviation)
VCP_TIGHTENING_MAX_DAYS = 20 # Max days for the final tight consolidation before breakout


# -- Power Play Setup Parameters --
PP_LOOKBACK_PERIOD = "1y"  # Data period to fetch for analysis

# 1. Trend Filter
PP_TREND_SMA_LONG = 200
PP_TREND_SMA_SHORT = 50
PP_TREND_52W_HIGH_THRESHOLD = 0.75  # Price must be within 25% of 52-week high
PP_RS_LOOKBACK = "6mo" # Relative Strength lookback period vs. S&P500

# 2. Setup Detection (Volatility & Volume)
PP_SETUP_BB_LENGTH = 20
PP_SETUP_BB_STD = 2.0
PP_SETUP_BBW_LOOKBACK = "6mo" # Lookback to find min Bollinger Band Width
PP_SETUP_ATR_LENGTH = 14
PP_SETUP_VOL_SMA_SHORT = 5
PP_SETUP_VOL_SMA_LONG = 50

# 3. Entry Trigger (Breakout)
PP_TRIGGER_HIGH_LOOKBACK = 50 # Days to look back for a new high
PP_TRIGGER_VOL_INCREASE_FACTOR = 1.5 # Breakout day volume must be >= 1.5x average

# 4. Confirmation (Indicators)
PP_CONFIRM_RSI_LENGTH = 14
PP_CONFIRM_RSI_MIN = 50.0
PP_CONFIRM_RSI_MAX = 70.0
PP_CONFIRM_MACD_FAST = 12
PP_CONFIRM_MACD_SLOW = 26
PP_CONFIRM_MACD_SIGNAL = 9
