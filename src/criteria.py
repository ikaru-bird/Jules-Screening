from src import config

def check_price(ticker_info):
    """Checks if the stock price is above the minimum threshold."""
    try:
        price = ticker_info.get('currentPrice')
        if price is not None and price >= config.MIN_PRICE:
            return True, f"Price {price:.2f} >= {config.MIN_PRICE}"
        return False, f"Price {price} < {config.MIN_PRICE}"
    except Exception:
        return False, "Could not check price"

def check_roe(ticker_info):
    """Checks if the Return on Equity is above the minimum threshold."""
    try:
        roe = ticker_info.get('returnOnEquity')
        if roe is not None and roe >= config.MIN_ROE:
            return True, f"ROE {roe:.2f} >= {config.MIN_ROE}"
        return False, f"ROE {roe} < {config.MIN_ROE}"
    except Exception:
        return False, "Could not check ROE"

def check_quarterly_eps_growth(ticker):
    """Checks if the most recent quarterly EPS has grown sufficiently YoY."""
    try:
        q_earnings = ticker.quarterly_earnings
        if q_earnings is None or len(q_earnings) < 5:
            return False, "Not enough quarterly data"

        latest_eps = q_earnings['Earnings'].iloc[-1]
        eps_year_ago = q_earnings['Earnings'].iloc[-5]

        if eps_year_ago > 0:
            growth = (latest_eps - eps_year_ago) / eps_year_ago
            if growth >= config.MIN_Q_EPS_GROWTH:
                return True, f"Quarterly EPS Growth {growth:.2f} >= {config.MIN_Q_EPS_GROWTH}"
        return False, "Negative or zero base EPS for quarterly growth"
    except Exception:
        return False, "Error calculating quarterly EPS growth"

def check_annual_eps_growth(ticker):
    """Checks if the 3-year average annual EPS growth (CAGR) is sufficient."""
    try:
        financials = ticker.financials
        if financials is None or financials.shape[1] < 4:
            return False, "Not enough annual financial data"

        if 'Basic EPS' in financials.index:
            eps_data = financials.loc['Basic EPS'].dropna()
            if len(eps_data) >= 4:
                # Use the last 4 available data points for a 3-year period
                eps_start = eps_data.iloc[-4]
                eps_end = eps_data.iloc[-1]
                if eps_start > 0 and eps_end > 0:
                    # CAGR = (Ending Value / Beginning Value)^(1 / Number of Years) - 1
                    cagr = ((eps_end / eps_start) ** (1/3)) - 1
                    if cagr >= config.MIN_ANNUAL_EPS_GROWTH_CAGR:
                        return True, f"3Y EPS CAGR {cagr:.2f} >= {config.MIN_ANNUAL_EPS_GROWTH_CAGR}"
        return False, "Could not calculate 3-year EPS CAGR"
    except Exception:
        return False, "Error calculating annual EPS growth"
