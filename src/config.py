"""
Configuration file for the stock screener application.

This file centralizes all the settings, thresholds, and parameters
used throughout the application, making it easy to adjust the behavior
of the scraper, financial checks, and pattern recognition logic.
"""

# -- General Settings --
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
HANDLE_MAX_DURATION_DAYS = 60 # 12 weeks
HANDLE_MIN_DURATION_DAYS = 5   # 1 week
# Defines the allowable pullback of the handle relative to the cup's high.
# e.g., MIN=0.85 allows a pullback of up to 15%.
HANDLE_DEPTH_MIN_FACTOR = 0.85 # Max pullback depth
HANDLE_DEPTH_MAX_FACTOR = 1.00 # Handle shouldn't be higher than the cup's high

# Pivot (breakout) parameters
PIVOT_LOOKAHEAD_DAYS = 30    # How many days to look for a pivot breakout after the handle
VOLUME_BREAKOUT_FACTOR = 1.5 # Volume on breakout day must be 1.5x the 50-day average
