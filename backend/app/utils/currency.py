from typing import Optional


CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "CA$",
    "AUD": "AU$",
    "INR": "₹",
    "JPY": "¥",
}


def format_currency(value: Optional[float], currency: str = "USD") -> str:
    """Formats a float value into a standard currency string."""
    if value is None:
        return "N/A"
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), f"{currency} ")
    if value < 0:
        return f"-{symbol}{abs(value):,.2f}"
    return f"{symbol}{value:,.2f}"


def format_percentage(value: Optional[float]) -> str:
    """Formats float value as a percentage with sign."""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"
