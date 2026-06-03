import numpy as np
import pandas as pd


def annualized_return(returns: pd.Series, periods_per_year: int = 12) -> float:
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    cumulative = (1 + returns).prod()
    years = len(returns) / periods_per_year
    if years <= 0:
        return np.nan
    return cumulative ** (1 / years) - 1


def annualized_volatility(returns: pd.Series, periods_per_year: int = 12) -> float:
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    return returns.std(ddof=1) * np.sqrt(periods_per_year)


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02, periods_per_year: int = 12) -> float:
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    rf_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess = returns - rf_period
    vol = returns.std(ddof=1)
    if vol == 0 or np.isnan(vol):
        return np.nan
    return excess.mean() / vol * np.sqrt(periods_per_year)


def max_drawdown(nav: pd.Series) -> float:
    nav = nav.dropna()
    if nav.empty:
        return np.nan
    peak = nav.cummax()
    drawdown = (nav - peak) / peak
    return drawdown.min()


def monthly_win_rate(returns: pd.Series) -> float:
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    return (returns > 0).sum() / len(returns)


def rolling_sharpe(returns: pd.Series, window: int = 12, risk_free_rate: float = 0.02) -> pd.Series:
    rf_period = (1 + risk_free_rate) ** (1 / 12) - 1
    return returns.rolling(window).apply(
        lambda x: ((x - rf_period).mean() / x.std(ddof=1) * np.sqrt(12)) if len(x) == window and x.std(ddof=1) != 0 else np.nan,
        raw=False,
    )


def performance_table(results: dict, benchmark_returns: pd.Series) -> pd.DataFrame:
    records = []
    for name, data in results.items():
        monthly = data["monthly"]
        ann_ret = annualized_return(monthly["strategy_return"], periods_per_year=12)
        ann_vol = annualized_volatility(monthly["strategy_return"], periods_per_year=12)
        sharp = sharpe_ratio(monthly["strategy_return"], risk_free_rate=0.02, periods_per_year=12)
        mdd = max_drawdown(monthly["nav"])
        win = monthly_win_rate(monthly["strategy_return"])
        records.append({
            "策略": name,
            "年化收益率": ann_ret,
            "年化波动率": ann_vol,
            "夏普比率": sharp,
            "最大回撤": mdd,
            "月度胜率": win,
        })
    benchmark_ann = annualized_return(benchmark_returns, periods_per_year=12)
    benchmark_vol = annualized_volatility(benchmark_returns, periods_per_year=12)
    benchmark_sr = sharpe_ratio(benchmark_returns, risk_free_rate=0.02, periods_per_year=12)
    benchmark_nav = (1 + benchmark_returns).cumprod()
    benchmark_mdd = max_drawdown(benchmark_nav)
    records.append({
        "策略": "沪深300基准",
        "年化收益率": benchmark_ann,
        "年化波动率": benchmark_vol,
        "夏普比率": benchmark_sr,
        "最大回撤": benchmark_mdd,
        "月度胜率": monthly_win_rate(benchmark_returns),
    })
    return pd.DataFrame(records)


def format_percentage(x: float) -> str:
    if pd.isna(x):
        return "N/A"
    return f"{x * 100:.2f}%"
