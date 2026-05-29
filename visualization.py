import os
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd
import seaborn as sns


def set_chinese_font():
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False


def ensure_folder(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def plot_monthly_heatmap(returns_df: pd.DataFrame, filename: str, title: str):
    set_chinese_font()
    table = returns_df.copy()
    table["year"] = table["month"].dt.year
    table["month_num"] = table["month"].dt.month
    pivot = table.pivot(index="month_num", columns="year", values="strategy_return")
    plt.figure(figsize=(12, 6))
    sns.heatmap(pivot, annot=True, fmt=".2%", cmap="RdYlGn", center=0, cbar_kws={"format": PercentFormatter(xmax=1, decimals=0)})
    plt.title(title)
    plt.ylabel("月份")
    plt.xlabel("年份")
    ensure_folder(filename)
    plt.tight_layout()
    plt.savefig(filename, dpi=200)
    plt.close()


def plot_nav_curves(nav_dict: dict, filename: str, title: str):
    set_chinese_font()
    plt.figure(figsize=(12, 7))
    for name, nav in nav_dict.items():
        dates = nav["date"] if "date" in nav.columns else nav.index
        values = nav["nav"] if "nav" in nav.columns else nav
        # 归一化到初始净值 1，便于不同尺度的组合在同一图中可视比较
        try:
            v = values.astype(float)
            if len(v) > 0 and v.iloc[0] != 0 and not pd.isna(v.iloc[0]):
                v = v / v.iloc[0]
        except Exception:
            v = values
        plt.plot(dates, v, label=name, linewidth=2)
    plt.title(title)
    plt.xlabel("时间")
    plt.ylabel("净值")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.xticks(rotation=30)
    plt.tight_layout()
    ensure_folder(filename)
    plt.savefig(filename, dpi=200)
    plt.close()


def plot_rolling_sharpe(rolling_dict: dict, filename: str, title: str):
    set_chinese_font()
    plt.figure(figsize=(12, 7))
    for name, series in rolling_dict.items():
        plt.plot(series.index.to_timestamp(), series.values, label=name)
    plt.axhline(0, color="black", linewidth=0.8, linestyle="--")
    plt.title(title)
    plt.xlabel("时间")
    plt.ylabel("滚动12个月夏普比")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()
    ensure_folder(filename)
    plt.savefig(filename, dpi=200)
    plt.close()


def plot_recent_3y_daily_returns(returns_df: pd.DataFrame, filename: str, title: str):
    """
    绘制近三年日度累计收益比较。
    `returns_df`：索引为日期的 DataFrame，列为各策略的日收益率（简单收益率）。
    """
    set_chinese_font()
    df = returns_df.copy()
    df = df.sort_index()
    # 计算累积净值（起点为1）
    cum = (1 + df).cumprod()
    plt.figure(figsize=(12, 7))
    for col in cum.columns:
        plt.plot(cum.index, cum[col] / cum.iloc[0][col], label=col)
    plt.title(title)
    plt.xlabel("时间")
    plt.ylabel("近3年累计净值（起点=1）")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.xticks(rotation=30)
    plt.tight_layout()
    ensure_folder(filename)
    plt.savefig(filename, dpi=200)
    plt.close()


def plot_10d_return_heatmap(strategy_series: pd.Series, filename: str, title: str, years: int = 3):
    """
    绘制近几年每10个交易日累计收益的热力图。
    `strategy_series`：索引为日期的 Series，值为日收益率。
    `years`：向前取多少年数据进行绘图。
    """
    set_chinese_font()
    df = strategy_series.dropna().sort_index().to_frame(name='daily_return')
    if not df.empty:
        last_date = df.index.max()
        start_date = last_date - pd.DateOffset(years=years)
        df = df[df.index >= start_date]
    df['year'] = df.index.year
    df['block'] = df.groupby('year').cumcount() // 10 + 1
    grouped = df.groupby(['year', 'block'])['daily_return'].apply(lambda x: (1 + x).prod() - 1).reset_index()
    pivot = grouped.pivot(index='block', columns='year', values='daily_return')
    plt.figure(figsize=(12, 8))
    sns.heatmap(pivot, annot=True, fmt='.2%', cmap='RdYlGn', center=0, cbar_kws={'format': PercentFormatter(xmax=1, decimals=0)}, annot_kws={"fontsize": 8})
    plt.title(title)
    plt.xlabel('年份')
    plt.ylabel('10 日交易日区间序号')
    plt.tight_layout()
    ensure_folder(filename)
    plt.savefig(filename, dpi=200)
    plt.close()
