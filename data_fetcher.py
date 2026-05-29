# requirements: pandas numpy akshare tqdm
import os
from datetime import datetime

import akshare as ak
import numpy as np
import pandas as pd
from tqdm import tqdm


def normalize_symbol(code: str) -> str:
    code = code.strip()
    if code.endswith(".SH") or code.endswith(".SZ"):
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


def ak_symbol(code: str) -> str:
    code = code.strip().upper().replace(".SH", "").replace(".SZ", "")
    if code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


def get_hs300_stocks(top_n: int = 200) -> list:
    df = ak.index_stock_cons(symbol="000300")
    if df is None or df.empty:
        raise ValueError("无法获取沪深300成分股列表，请检查 akshare 接口是否可用")
    if "品种代码" in df.columns:
        codes = df["品种代码"].astype(str).tolist()
    elif "代码" in df.columns:
        codes = df["代码"].astype(str).tolist()
    else:
        codes = df.iloc[:, 0].astype(str).tolist()
    codes = [normalize_symbol(c) for c in codes]
    return codes[:top_n]


def fetch_daily_stock(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    ak_sym = ak_symbol(symbol)
    try:
        df = ak.stock_zh_a_daily(symbol=ak_sym, start_date=start_date, end_date=end_date, adjust="hfq")
    except Exception:
        df = ak.stock_zh_a_daily(symbol=ak_sym, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["code"] = normalize_symbol(symbol)
    df["adj_close"] = df["close"]
    return df[["date", "code", "open", "high", "low", "close", "adj_close", "volume", "amount"]]


def fetch_benchmark(index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    # akshare 提供的指数日线接口为 stock_zh_index_daily，symbol 需带交易所前缀，例如 sh000300
    code = index_code.upper().replace(".SH", "").replace(".SZ", "")
    if code.startswith("000") or code.startswith("399") or code.startswith("00"):
        # 将常见指数代码转换为 akshare 要求的格式
        if index_code.endswith(".SH") or code.startswith("000"):
            sym = f"sh{code}"
        else:
            sym = f"sz{code}"
    else:
        sym = f"sh{code}"
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
    except Exception:
        df = None
    if df is None or df.empty:
        raise ValueError(f"无法获取基准指数 {index_code} 的日线数据，尝试的 symbol={sym}")
    # 统一列名并筛选时间区间
    if "date" not in df.columns:
        # 有些接口返回中文列名
        rename_map = {c: c for c in df.columns}
        lower = [c.lower() for c in df.columns]
        if "日期" in df.columns:
            df = df.rename(columns={"日期": "date"})
        elif "time" in lower:
            for c in df.columns:
                if c.lower() == "time":
                    df = df.rename(columns={c: "date"})
                    break
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[(df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))]
    # ak 的指数数据列可能为 close 或收盘
    if "close" in df.columns:
        df["return"] = df["close"].pct_change()
    elif "收盘" in df.columns:
        df = df.rename(columns={"收盘": "close"})
        df["return"] = df["close"].pct_change()
    else:
        raise ValueError("无法识别基准数据中的收盘价字段")
    return df[["date", "close", "return"]]


def fetch_daily_basic(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    ak_sym = ak_symbol(symbol)
    try:
        df = ak.stock_zh_a_daily_basic(symbol=ak_sym, start_date=start_date, end_date=end_date)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    rename_map = {
        "日期": "date",
        "总市值": "total_mv",
        "流通市值": "circ_mv",
        "市盈率(TTM)": "pe_ttm",
        "市盈率TTM": "pe_ttm",
        "市净率": "pb",
    }
    df = df.rename(columns=rename_map)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["code"] = normalize_symbol(symbol)
    return df[["date", "code", "total_mv", "circ_mv", "pe_ttm", "pb"]]


def build_basic_panel(symbols: list, start_date: str, end_date: str, cache_dir: str = "data_cache") -> pd.DataFrame:
    os.makedirs(cache_dir, exist_ok=True)
    frames = []
    for symbol in tqdm(symbols, desc="Downloading fundamental data"):
        code = normalize_symbol(symbol)
        cache_file = os.path.join(cache_dir, f"basic_{code.replace('.', '_')}.csv")
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=["date"])
        else:
            df = fetch_daily_basic(code, start_date, end_date)
            if not df.empty:
                df.to_csv(cache_file, index=False)
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["date", "code"]).reset_index(drop=True)
    return all_df


def merge_month_end_fundamentals(month_end_df: pd.DataFrame, basic_panel: pd.DataFrame) -> pd.DataFrame:
    if basic_panel is None or basic_panel.empty:
        month_end_df["total_mv"] = np.nan
        month_end_df["pb"] = np.nan
        month_end_df["pe_ttm"] = np.nan
        return month_end_df
    basic_panel = basic_panel.copy()
    basic_panel["month"] = basic_panel["date"].dt.to_period("M")
    month_basic = basic_panel.groupby(["code", "month"]).last().reset_index()
    merged = month_end_df.merge(month_basic[["code", "month", "total_mv", "pb", "pe_ttm"]], on=["code", "month"], how="left")
    return merged


def build_price_panel(symbols: list, start_date: str, end_date: str, cache_dir: str = "data_cache") -> pd.DataFrame:
    os.makedirs(cache_dir, exist_ok=True)
    frames = []
    for symbol in tqdm(symbols, desc="Downloading price data"):
        code = normalize_symbol(symbol)
        cache_file = os.path.join(cache_dir, f"{code.replace('.', '_')}.csv")
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=["date"])
        else:
            df = fetch_daily_stock(code, start_date, end_date)
            if not df.empty:
                df.to_csv(cache_file, index=False)
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        raise RuntimeError("未获取到任何股票数据")
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.drop_duplicates(subset=["date", "code"]).reset_index(drop=True)
    return all_df


def standardize_panel(all_df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    date_index = pd.to_datetime(sorted(all_df["date"].unique()))
    codes = sorted(all_df["code"].unique())
    full_index = pd.MultiIndex.from_product([date_index, codes], names=["date", "code"])
    panel = all_df.set_index(["date", "code"]).reindex(full_index)
    panel = panel.sort_index()
    panel[["open", "high", "low", "close", "adj_close", "volume", "amount"]] = panel[["open", "high", "low", "close", "adj_close", "volume", "amount"]].astype(float)
    panel = panel.reset_index()
    panel = panel[panel["date"].between(pd.to_datetime(start_date), pd.to_datetime(end_date))]
    return panel


def fill_forward_panel(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["code", "date"]).copy()
    panel[["open", "high", "low", "close", "adj_close", "volume", "amount"]] = panel.groupby("code")[["open", "high", "low", "close", "adj_close", "volume", "amount"]].fillna(method="ffill")
    return panel


def exclude_low_frequency(panel: pd.DataFrame, max_missing_ratio: float = 0.2) -> pd.DataFrame:
    trading_dates = sorted(panel["date"].unique())
    total_days = len(trading_dates)
    valid_codes = []
    for code, group in panel.groupby("code"):
        present_days = group[~group["close"].isna()].shape[0]
        if present_days / total_days >= (1 - max_missing_ratio):
            valid_codes.append(code)
    return panel[panel["code"].isin(valid_codes)].copy()


def drop_long_missing_segments(panel: pd.DataFrame, max_gap: int = 5) -> pd.DataFrame:
    keep_codes = []
    for code, group in panel.groupby("code"):
        missing = group["close"].isna().astype(int).values
        ranks = np.diff(np.concatenate(([0], missing, [0])))
        starts = np.where(ranks == 1)[0]
        ends = np.where(ranks == -1)[0]
        longest_missing = 0
        for s, e in zip(starts, ends):
            longest_missing = max(longest_missing, e - s)
        if longest_missing <= max_gap:
            keep_codes.append(code)
    return panel[panel["code"].isin(keep_codes)].copy()


def compute_features(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["close"] = panel["close"].astype(float)
    panel["adj_close"] = panel["adj_close"].astype(float)
    panel.sort_values(["code", "date"], inplace=True)
    panel["ret_daily"] = panel.groupby("code")["adj_close"].pct_change()
    panel["high_52w"] = panel.groupby("code")["adj_close"].transform(lambda x: x.rolling(252, min_periods=252).max())
    panel["pth"] = panel["adj_close"] / panel["high_52w"]
    panel["ret_1m"] = panel.groupby("code")["adj_close"].transform(lambda x: x.pct_change(21))
    panel["ret_6m"] = panel.groupby("code")["adj_close"].transform(lambda x: x.shift(21).pct_change(126))
    panel["month"] = panel["date"].dt.to_period("M")
    return panel


def compute_monthly_returns(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["month"] = panel["date"].dt.to_period("M")
    grouped = panel.groupby(["code", "month"])
    monthly_price = grouped.last().reset_index()
    monthly_price["monthly_return"] = monthly_price.groupby("code")["adj_close"].pct_change()
    return monthly_price[["date", "code", "month", "adj_close", "monthly_return"]]


def get_month_end_features(panel: pd.DataFrame) -> pd.DataFrame:
    month_end = panel.groupby(["code", "month"]).last().reset_index()
    return month_end


def calculate_benchmark_returns(benchmark_df: pd.DataFrame) -> pd.DataFrame:
    benchmark_df = benchmark_df.copy()
    benchmark_df["month"] = benchmark_df["date"].dt.to_period("M")
    monthly = benchmark_df.groupby("month").last().reset_index()
    monthly["return"] = monthly["close"].pct_change()
    return monthly[["month", "close", "return"]]
