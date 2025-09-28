import yfinance as yf
from src import config

def get_quarterly_eps_growth_data(ticker: yf.Ticker):
    """
    Tries to calculate Year-over-Year quarterly EPS growth using multiple methods.

    Returns:
        A tuple containing:
        - The calculated growth rate (e.g., 0.25 for 25%) or None if it fails.
        - A string describing the method used or the reason for failure.
    """
    # Method 1: Use 'Basic EPS' from quarterly_financials
    try:
        q_financials = ticker.quarterly_financials
        if not q_financials.empty and 'Basic EPS' in q_financials.index and len(q_financials.columns) >= 5:
            eps_data = q_financials.loc['Basic EPS'].dropna()
            if len(eps_data) >= 5:
                latest_eps = eps_data.iloc[0]
                eps_year_ago = eps_data.iloc[4]
                if eps_year_ago > 0:
                    growth = (latest_eps - eps_year_ago) / eps_year_ago
                    return growth, "Method: quarterly_financials['Basic EPS']"
    except Exception:
        pass  # Silently try next method

    # Method 2: Manual calculation using Net Income and Shares Outstanding
    try:
        q_financials = ticker.quarterly_financials
        info = ticker.info
        if (not q_financials.empty and 'Net Income' in q_financials.index and len(q_financials.columns) >= 5 and
                info and info.get('sharesOutstanding')):
            net_income = q_financials.loc['Net Income'].dropna()
            shares = info['sharesOutstanding']
            if len(net_income) >= 5 and shares > 0:
                manual_eps = net_income / shares
                latest_eps = manual_eps.iloc[0]
                eps_year_ago = manual_eps.iloc[4]
                if eps_year_ago > 0:
                    growth = (latest_eps - eps_year_ago) / eps_year_ago
                    return growth, "Method: Manual (Net Income / Shares)"
    except Exception:
        pass

    # Method 3: Use pre-calculated value from .info
    try:
        info = ticker.info
        if info and info.get('earningsQuarterlyGrowth') is not None:
            growth = info['earningsQuarterlyGrowth']
            return growth, "Method: info['earningsQuarterlyGrowth']"
    except Exception:
        pass

    return None, "Failure: Not enough quarterly data from any source"


def get_annual_eps_cagr_data(ticker: yf.Ticker, years: int = 3):
    """
    Tries to calculate the Compound Annual Growth Rate (CAGR) of EPS over a number of years.

    Args:
        ticker: The yfinance Ticker object.
        years: The number of years for the CAGR calculation.

    Returns:
        A tuple containing:
        - The calculated CAGR (e.g., 0.25 for 25%) or None if it fails.
        - A string describing the method used or the reason for failure.
    """
    required_data_points = years + 1

    # Method 1: Use 'Basic EPS' from financials
    try:
        financials = ticker.financials
        if not financials.empty and 'Basic EPS' in financials.index and len(financials.columns) >= required_data_points:
            eps_data = financials.loc['Basic EPS'].dropna()
            if len(eps_data) >= required_data_points:
                eps_end = eps_data.iloc[0]
                eps_start = eps_data.iloc[years]
                if eps_start > 0 and eps_end > 0:
                    cagr = ((eps_end / eps_start) ** (1/float(years))) - 1
                    return cagr, "Method: financials['Basic EPS']"
    except Exception:
        pass

    # Method 2: Manual calculation using Net Income and Shares Outstanding
    try:
        financials = ticker.financials
        info = ticker.info
        if (not financials.empty and 'Net Income' in financials.index and len(financials.columns) >= required_data_points and
                info and info.get('sharesOutstanding')):
            net_income = financials.loc['Net Income'].dropna()
            shares = info['sharesOutstanding']  # Approximation
            if len(net_income) >= required_data_points and shares > 0:
                manual_eps = net_income / shares
                eps_end = manual_eps.iloc[0]
                eps_start = manual_eps.iloc[years]
                if eps_start > 0 and eps_end > 0:
                    cagr = ((eps_end / eps_start) ** (1/float(years))) - 1
                    return cagr, "Method: Manual (Net Income / Shares)"
    except Exception:
        pass

    return None, f"Failure: Not enough annual data for {years}-year CAGR"


def get_annual_eps_yoy_growth_data(ticker: yf.Ticker):
    """
    Tries to calculate Year-over-Year annual EPS growth for the most recent year.

    Returns:
        A tuple containing:
        - The calculated growth rate (e.g., 0.25 for 25%) or None if it fails.
        - A string describing the method used or the reason for failure.
    """
    # Method 1: Use 'Basic EPS' from financials
    try:
        financials = ticker.financials
        if not financials.empty and 'Basic EPS' in financials.index and len(financials.columns) >= 2:
            eps_data = financials.loc['Basic EPS'].dropna()
            if len(eps_data) >= 2:
                latest_eps = eps_data.iloc[0]
                previous_eps = eps_data.iloc[1]
                if previous_eps > 0:
                    growth = (latest_eps - previous_eps) / previous_eps
                    return growth, "Method: financials['Basic EPS']"
    except Exception:
        pass  # Silently try next method

    # Method 2: Manual calculation using Net Income and Shares Outstanding
    try:
        financials = ticker.financials
        info = ticker.info
        if (not financials.empty and 'Net Income' in financials.index and len(financials.columns) >= 2 and
                info and info.get('sharesOutstanding')):
            net_income = financials.loc['Net Income'].dropna()
            shares = info['sharesOutstanding']
            if len(net_income) >= 2 and shares > 0:
                manual_eps = net_income / shares
                latest_eps = manual_eps.iloc[0]
                previous_eps = manual_eps.iloc[1]
                if previous_eps > 0:
                    growth = (latest_eps - previous_eps) / previous_eps
                    return growth, "Method: Manual (Net Income / Shares)"
    except Exception:
        pass

    return None, "Failure: Not enough annual data for YoY growth"


def check_price(ticker_info):
    """
    Checks if the stock price is above the minimum threshold.
    Returns (True, '--') if data is unavailable.
    """
    try:
        price = ticker_info.get('currentPrice')
        if price is None:
            return True, "--"  # Treat as OK if data is missing
        if price >= config.MIN_PRICE:
            return True, f"Price {price:.2f} >= {config.MIN_PRICE}"
        else:
            return False, f"Price {price:.2f} < {config.MIN_PRICE}"
    except Exception:
        return True, "--"  # Treat as OK on error

def check_roe(ticker_info):
    """
    Checks if the Return on Equity is above the minimum threshold.
    Returns (True, '--') if data is unavailable.
    """
    try:
        roe = ticker_info.get('returnOnEquity')
        if roe is None:
            return True, "--" # Treat as OK if data is missing
        if roe >= config.MIN_ROE:
            return True, f"{roe:.2%} >= {config.MIN_ROE:.0%}"
        else:
            return False, f"{roe:.2%} < {config.MIN_ROE:.0%}"
    except Exception:
        return True, "--" # Treat as OK on error

def check_quarterly_eps_growth(ticker: yf.Ticker):
    """
    Checks if the most recent quarterly EPS has grown sufficiently YoY.
    Returns (True, '--') if data is unavailable.
    """
    growth, reason = get_quarterly_eps_growth_data(ticker)

    if growth is None:
        return True, "--"  # Treat as OK if data is missing

    if growth >= config.MIN_Q_EPS_GROWTH:
        return True, f"{growth:.2%} >= {config.MIN_Q_EPS_GROWTH:.0%}"
    else:
        return False, f"{growth:.2%} < {config.MIN_Q_EPS_GROWTH:.0%}"

def check_annual_eps_growth(ticker: yf.Ticker):
    """
    Checks if the 3-year average annual EPS growth (CAGR) is sufficient.
    Returns (True, '--') if data is unavailable.
    """
    cagr, reason = get_annual_eps_cagr_data(ticker, years=3)

    if cagr is None:
        return True, "--"  # Treat as OK if data is missing

    if cagr >= config.MIN_ANNUAL_EPS_GROWTH_CAGR:
        return True, f"{cagr:.2%} >= {config.MIN_ANNUAL_EPS_GROWTH_CAGR:.0%}"
    else:
        return False, f"{cagr:.2%} < {config.MIN_ANNUAL_EPS_GROWTH_CAGR:.0%}"

def check_annual_eps_yoy_growth(ticker: yf.Ticker):
    """
    Checks if the most recent annual EPS has grown sufficiently YoY.
    Returns (True, '--') if data is unavailable.
    """
    growth, reason = get_annual_eps_yoy_growth_data(ticker)

    if growth is None:
        return True, "--"  # Treat as OK if data is missing

    if growth >= config.MIN_ANNUAL_EPS_YOY_GROWTH:
        return True, f"{growth:.2%} >= {config.MIN_ANNUAL_EPS_YOY_GROWTH:.0%}"
    else:
        return False, f"{growth:.2%} < {config.MIN_ANNUAL_EPS_YOY_GROWTH:.0%}"
