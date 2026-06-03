import pandas as pd


def compute_monthly_portfolio_returns(signals: pd.DataFrame, monthly_returns: pd.DataFrame) -> pd.DataFrame:
    merged = monthly_returns.merge(signals, on=["month", "code"], how="inner")
    merged = merged.dropna(subset=["monthly_return"])
    long_returns = merged[merged["signal"] == 1].groupby("month")["monthly_return"].mean()
    short_returns = merged[merged["signal"] == -1].groupby("month")["monthly_return"].mean()
    portfolio = pd.DataFrame({
        "long_return": long_returns,
        "short_return": short_returns,
    }).fillna(0)
    portfolio["strategy_return"] = portfolio["long_return"] - portfolio["short_return"]
    portfolio = portfolio.reset_index()
    return portfolio


def compute_daily_portfolio_returns(signals: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["daily_return"] = panel.groupby("code")["adj_close"].pct_change()
    panel["month"] = panel["date"].dt.to_period("M")
    merged = panel.merge(signals, on=["month", "code"], how="inner")
    merged = merged.dropna(subset=["daily_return"])
    grouped = merged.groupby(["date", "signal"])["daily_return"].mean().unstack(fill_value=0)
    grouped.columns = [f"signal_{int(col)}" for col in grouped.columns]
    grouped = grouped.sort_index()
    grouped["daily_return"] = grouped.get("signal_1", 0) - grouped.get("signal_-1", 0)
    grouped = grouped[["daily_return"]]
    grouped["nav"] = (1 + grouped["daily_return"]).cumprod()
    grouped = grouped.reset_index()
    return grouped


def run_backtest(strategy_name: str, signals: pd.DataFrame, monthly_returns: pd.DataFrame, price_panel: pd.DataFrame) -> dict:
    monthly_port = compute_monthly_portfolio_returns(signals, monthly_returns)
    monthly_port["nav"] = (1 + monthly_port["strategy_return"]).cumprod()
    daily_port = compute_daily_portfolio_returns(signals, price_panel)
    return {
        "strategy": strategy_name,
        "monthly": monthly_port,
        "daily": daily_port,
    }
