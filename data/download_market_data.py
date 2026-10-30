import yfinance as yf


ticker = "GOLDBEES.NS"

data = yf.download(
    ticker,
    start="2020-01-01",
    end="2026-01-01",
    auto_adjust=True
)

close_prices = data["Close"].squeeze()

daily_returns = close_prices.pct_change().dropna()

annual_return = daily_returns.mean() * 252
annual_volatility = daily_returns.std() * (252 ** 0.5)

historical_data = close_prices.to_frame(name="close")

historical_data.to_csv(
    "data/goldbees_historical.csv"
)

print("Historical data saved successfully.")

print("Number of price observations:",
      len(close_prices))

print("Annualized return:",
      round(annual_return * 100, 2), "%")

print("Annualized volatility:",
      round(annual_volatility * 100, 2), "%") 