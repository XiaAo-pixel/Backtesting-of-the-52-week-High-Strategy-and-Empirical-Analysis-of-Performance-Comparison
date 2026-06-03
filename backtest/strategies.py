import numpy as np
import pandas as pd


def rank_groups(group: pd.DataFrame, indicator: str, n_groups: int = 10, ascending: bool = True) -> pd.DataFrame:
    group = group.copy()
    group["rank_pct"] = group[indicator].rank(method="first", pct=True, ascending=ascending)
    try:
        group["group"] = pd.qcut(group["rank_pct"], q=n_groups, labels=False, duplicates="drop") + 1
    except Exception:
        group["group"] = pd.cut(group["rank_pct"], bins=n_groups, labels=False, include_lowest=True) + 1
    return group


def generate_52wh_signal(month_end_df: pd.DataFrame) -> pd.DataFrame:
    df = month_end_df.copy()
    df = df.dropna(subset=["pth"])
    signals = []
    for month, group in df.groupby("month"):
        ranked = rank_groups(group, indicator="pth", n_groups=10, ascending=True)
        long = ranked[ranked["group"] == 10]["code"].tolist()
        short = ranked[ranked["group"] == 1]["code"].tolist()
        signals.append(pd.DataFrame({"month": month, "code": long, "signal": 1}))
        signals.append(pd.DataFrame({"month": month, "code": short, "signal": -1}))
    res = pd.concat(signals, ignore_index=True)
    # 按照回测设定：在 t 月末使用数据决定下个月持仓，故 month 向前移动一个月
    res["month"] = res["month"].apply(lambda x: x + 1)
    return res


def generate_mom_signal(month_end_df: pd.DataFrame) -> pd.DataFrame:
    df = month_end_df.copy()
    df = df.dropna(subset=["ret_6m"])
    signals = []
    for month, group in df.groupby("month"):
        ranked = rank_groups(group, indicator="ret_6m", n_groups=10, ascending=True)
        long = ranked[ranked["group"] == 10]["code"].tolist()
        short = ranked[ranked["group"] == 1]["code"].tolist()
        signals.append(pd.DataFrame({"month": month, "code": long, "signal": 1}))
        signals.append(pd.DataFrame({"month": month, "code": short, "signal": -1}))
    res = pd.concat(signals, ignore_index=True)
    res["month"] = res["month"].apply(lambda x: x + 1)
    return res


def generate_rev_signal(month_end_df: pd.DataFrame) -> pd.DataFrame:
    df = month_end_df.copy()
    df = df.dropna(subset=["ret_1m"])
    signals = []
    for month, group in df.groupby("month"):
        ranked = rank_groups(group, indicator="ret_1m", n_groups=10, ascending=True)
        long = ranked[ranked["group"] == 1]["code"].tolist()
        short = ranked[ranked["group"] == 10]["code"].tolist()
        signals.append(pd.DataFrame({"month": month, "code": long, "signal": 1}))
        signals.append(pd.DataFrame({"month": month, "code": short, "signal": -1}))
    res = pd.concat(signals, ignore_index=True)
    res["month"] = res["month"].apply(lambda x: x + 1)
    return res


def generate_ff5_signal(month_end_df: pd.DataFrame) -> pd.DataFrame:
    """生成 FF5 简化三因子信号（价值 + 盈利 + 投资）。

    使用月度末数据构建三因子等权评分：
    - 价值因子 (BM): 市净率倒数 1/PB，高 BM = 价值股
    - 盈利因子: 优先使用 ROE（来自季度财务报告），
      若不可用则退化为盈利收益率 EY = 1/PE_TTM
    - 投资因子 (INV): 总市值 12 个月变化率，低增长 = 保守型

    策略做多得分最高的 30% 股票，做空得分最低的 30% 股票。
    注意：此为简化版 FF5 代理，缺少规模因子 (SMB) 和市场因子，
    且基本面数据覆盖率因 akshare 接口限制可能不完整。
    """
    df = month_end_df.copy()
    # 价值因子：市净率倒数 (Book-to-Market)
    df["pb"] = df["pb"].replace(0, np.nan)
    df["bm"] = 1 / df["pb"]

    # 盈利因子：优先使用 ROE，否则使用盈利收益率 (1/PE_TTM)
    if "roe" in df.columns and df["roe"].notna().sum() > 10:
        df["profitability"] = df["roe"]
    else:
        df["ey"] = 1 / df["pe_ttm"]  # 盈利收益率 Earnings Yield
        df["ey"] = df["ey"].replace([np.inf, -np.inf], np.nan)
        df["profitability"] = df["ey"]

    # 投资因子：总市值 12 个月增长（增长低的保守型公司得分高）
    df["inv"] = df.groupby("code")["total_mv"].pct_change(12, fill_method=None)
    df["inv"] = df["inv"].fillna(0)

    # 排名：BM 和盈利性越高越好，投资增长越低越好
    df["bm_rank"] = df.groupby("month")["bm"].rank(pct=True, ascending=False)
    df["profit_rank"] = df.groupby("month")["profitability"].rank(pct=True, ascending=False)
    df["inv_rank"] = df.groupby("month")["inv"].rank(pct=True, ascending=True)
    df["bm_rank"] = df["bm_rank"].fillna(0.5)
    df["profit_rank"] = df["profit_rank"].fillna(0.5)
    df["inv_rank"] = df["inv_rank"].fillna(0.5)
    df["ff5_score"] = (df["bm_rank"] + df["profit_rank"] + df["inv_rank"]) / 3

    signals = []
    for month, group in df.groupby("month"):
        group = group.dropna(subset=["ff5_score"])
        if group.empty:
            continue
        group = group.sort_values("ff5_score", ascending=False).reset_index(drop=True)
        n = len(group)
        cutoff = max(int(n * 0.3), 1)
        long = group.head(cutoff)["code"].tolist()
        short = group.tail(cutoff)["code"].tolist()
        signals.append(pd.DataFrame({"month": month, "code": long, "signal": 1}))
        signals.append(pd.DataFrame({"month": month, "code": short, "signal": -1}))
    res = pd.concat(signals, ignore_index=True)
    res["month"] = res["month"].apply(lambda x: x + 1)
    return res
