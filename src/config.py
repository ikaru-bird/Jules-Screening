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
MIN_PRICE = 10.00
MIN_ROE = 0.15
MIN_Q_EPS_GROWTH = 0.25
MIN_ANNUAL_EPS_GROWTH_CAGR = 0.25

# -- Cup With Handle (CWH) Pattern Parameters --
CWH_LOOKBACK_PERIOD = "2y" # Data period to fetch for pattern analysis

# Cup parameters
CUP_MIN_DEPTH_FACTOR = 1.3 # The peak of the cup must be at least 30% higher than the bottom.

# Base (consolidation period) parameters
# Defines the allowable range for the base consolidation, relative to the cup's high.
# e.g., MIN_FACTOR=0.75 means the base can't be deeper than 25% from the high.
BASE_DEPTH_MIN_FACTOR = 0.75 # Max depth of consolidation relative to cup peak
BASE_DEPTH_MAX_FACTOR = 1.05 # Max height of consolidation relative to cup peak
BASE_MIN_DURATION_DAYS = 49  # 7 weeks
BASE_MAX_DURATION_DAYS = 455 # 65 weeks
BASE_MAX_VOLATILITY = 0.15   # Max price volatility (std dev / mean) during base formation

# Cup lip formation parameters
CUP_LIP_MIN_FACTOR = 0.95 # The price should approach the old high
CUP_LIP_MAX_FACTOR = 1.05 # But not exceed it by too much before the handle

# Handle parameters
HANDLE_MAX_DURATION_DAYS = 60
HANDLE_MIN_DURATION_DAYS = 5
# Defines the allowable pullback of the handle.
# e.g., MIN=0.85 allows a pullback of up to 15% from the handle's peak.
# e.g., MAX=0.98 requires a pullback of at least 2%.
HANDLE_DEPTH_MIN_FACTOR = 0.85 # How far the handle can pull back from its own little peak
HANDLE_DEPTH_MAX_FACTOR = 0.98

# Pivot (breakout) parameters
PIVOT_LOOKAHEAD_DAYS = 30    # How many days to look for a pivot breakout after the handle
VOLUME_BREAKOUT_FACTOR = 1.5 # Volume on breakout day must be 1.5x the 50-day average
