# requirements: pandas numpy akshare tqdm
import os
import time
from datetime import datetime

import akshare as ak
import numpy as np
import pandas as pd
from tqdm import tqdm


def normalize_symbol(code: str) -> str:
    """标准化股票代码为 'XXXXXX.SH' 或 'XXXXXX.SZ' 格式"""
    code = code.strip()
    if code.endswith(".SH") or code.endswith(".SZ"):
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


def ak_symbol(code: str) -> str:
    """转换为 akshare 通用股票代码格式（如 sh600000, sz000001）"""
    code = code.strip().upper().replace(".SH", "").replace(".SZ", "")
    if code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


def ak_symbol_digits(code: str) -> str:
    """提取纯数字股票代码（如 000001, 600000）"""
    return code.strip().upper().replace(".SH", "").replace(".SZ", "")


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


def fetch_daily_valuation(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过 akshare 百度估值接口获取个股每日 PB 和总市值数据。

    由于 stock_zh_a_daily_basic 在新版 akshare 中已移除，
    改用 stock_zh_valuation_baidu 分别获取市净率和总市值。
    """
    code_digits = ak_symbol_digits(symbol)
    result = pd.DataFrame()

    # 获取市净率 (PB)
    try:
        pb_df = ak.stock_zh_valuation_baidu(symbol=code_digits, indicator="市净率", period="近十年")
        if pb_df is not None and not pb_df.empty:
            pb_df = pb_df.rename(columns={"value": "pb"})
            pb_df["date"] = pd.to_datetime(pb_df["date"])
            result = pb_df[["date", "pb"]].copy()
    except Exception:
        pass

    # 获取总市值
    try:
        mv_df = ak.stock_zh_valuation_baidu(symbol=code_digits, indicator="总市值", period="近十年")
        if mv_df is not None and not mv_df.empty:
            mv_df = mv_df.rename(columns={"value": "total_mv"})
            mv_df["date"] = pd.to_datetime(mv_df["date"])
            if result.empty:
                result = mv_df[["date", "total_mv"]].copy()
            else:
                result = result.merge(mv_df[["date", "total_mv"]], on="date", how="outer")
    except Exception:
        pass

    if result.empty:
        return pd.DataFrame()

    result = result.sort_values("date").reset_index(drop=True)
    result = result[(result["date"] >= pd.to_datetime(start_date)) & (result["date"] <= pd.to_datetime(end_date))]
    result["code"] = normalize_symbol(symbol)
    result["circ_mv"] = np.nan  # 百度接口不提供流通市值
    result["pe_ttm"] = np.nan   # 百度接口市盈率不稳定，后续从财务数据推导
    return result[["date", "code", "total_mv", "circ_mv", "pe_ttm", "pb"]]


def fetch_quarterly_financial(symbol: str) -> pd.DataFrame:
    """获取个股季度财务数据（净利润、每股净资产、ROE 等）。

    使用 akshare 同花顺财务摘要接口。
    返回 DataFrame 包含报告期、净资产收益率等关键指标。
    """
    code_digits = ak_symbol_digits(symbol)
    try:
        df = ak.stock_financial_abstract_ths(symbol=code_digits, indicator="按报告期")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    # 同花顺接口列名在控制台可能显示乱码，按位置选取更可靠
    # 列顺序: 报告期(0), 净利润(1), ..., 每股净资产(8), ..., 净资产收益率(13)
    cols = df.columns.tolist()
    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df.iloc[:, 0])

    # 尝试通过列名匹配，失败则按位置取
    col_map_source = {
        "净利润": "net_profit",
        "每股净资产": "bps",
        "净资产收益率": "roe",
    }
    # 建立实际列名到标准名的映射
    for actual_col in cols:
        for key, val in col_map_source.items():
            if key in actual_col:
                result[val] = df[actual_col]
                col_map_source.pop(key)
                break

    # 如果列名匹配失败则按位置提取
    if "net_profit" not in result.columns and len(cols) > 1:
        result["net_profit"] = df.iloc[:, 1]
    if "bps" not in result.columns and len(cols) > 8:
        result["bps"] = df.iloc[:, 8]
    if "roe" not in result.columns and len(cols) > 13:
        result["roe"] = df.iloc[:, 13]

    result["code"] = normalize_symbol(symbol)
    # 清洗：净利润和每股净资产中的单位（万/亿）作为字符串混在数值中
    for col in ["net_profit", "bps", "roe"]:
        if col in result.columns:
            result[col] = result[col].astype(str).str.replace("亿", "e8").str.replace("万", "e4")
            result[col] = result[col].str.replace("%", "").str.replace(",", "")
            result[col] = pd.to_numeric(result[col], errors="coerce")
            # 将带有 e8/e4 标记的数值转换为实际数值
            if col in result.columns:
                mask_e8 = result[col].astype(str).str.contains("e8", na=False)
                mask_e4 = result[col].astype(str).str.contains("e4", na=False)
                result[col] = pd.to_numeric(result[col].astype(str).str.replace("e8", "").str.replace("e4", ""), errors="coerce")
                result.loc[mask_e8, col] = result.loc[mask_e8, col] * 1e8
                result.loc[mask_e4, col] = result.loc[mask_e4, col] * 1e4

    return result[["date", "code", "net_profit", "bps", "roe"]]


def build_basic_panel(symbols: list, start_date: str, end_date: str, cache_dir: str = "data_cache") -> pd.DataFrame:
    """构建基本面面板数据（PB、总市值、PE_TTM）。

    从百度估值接口获取每日 PB 和总市值；
    从同花顺财务摘要获取季度 ROE 和每股净资产；
    结合两者推导 PE_TTM = PB / ROE（基于最新季度 ROE 前向填充）。
    """
    os.makedirs(cache_dir, exist_ok=True)
    frames = []
    for symbol in tqdm(symbols, desc="Downloading fundamental data"):
        code = normalize_symbol(symbol)
        cache_file = os.path.join(cache_dir, f"basic_{code.replace('.', '_')}.csv")
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=["date"])
        else:
            df = fetch_daily_valuation(code, start_date, end_date)
            if df.empty:
                continue
            # 获取季度财务数据并推导 PE_TTM
            fin_df = fetch_quarterly_financial(code)
            if not fin_df.empty:
                # 将季度 ROE 前向填充到每日
                fin_df = fin_df.sort_values("date")
                # 创建日期到 ROE 的映射：每个报告期的 ROE 覆盖到下一个报告期
                daily_dates = pd.date_range(start=df["date"].min(), end=df["date"].max(), freq="D")
                roe_series = pd.Series(index=daily_dates, dtype=float)
                for _, row in fin_df.iterrows():
                    report_date = row["date"]
                    # 财务报告通常在季度结束后 1-2 个月发布
                    # 为保守起见，假设报告在季度结束后 60 天可用
                    effective_date = report_date + pd.Timedelta(days=60)
                    if effective_date < daily_dates[0]:
                        effective_date = daily_dates[0]
                    roe_series[effective_date:] = row["roe"] if pd.notna(row["roe"]) else roe_series[effective_date:]
                # 将 ROE 映射到实际交易日
                roe_daily = pd.DataFrame({"date": pd.to_datetime(df["date"]), "roe_fwd": np.nan})
                for i, d in enumerate(roe_daily["date"]):
                    if d in roe_series.index:
                        roe_daily.loc[roe_daily.index[i], "roe_fwd"] = roe_series[d]
                roe_daily["roe_fwd"] = roe_daily["roe_fwd"].ffill()
                df = df.merge(roe_daily, on="date", how="left")
            else:
                df["roe_fwd"] = np.nan

            # 推导 PE_TTM = PB / ROE（当 ROE 和 PB 均可用时）
            if "roe_fwd" in df.columns and "pb" in df.columns:
                # ROE 是百分比（如 10.5 表示 10.5%），需除以 100
                df["pe_ttm"] = np.where(
                    (df["roe_fwd"].notna()) & (df["pb"].notna()) & (df["roe_fwd"] > 0),
                    df["pb"] / (df["roe_fwd"] / 100),
                    np.nan
                )
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
    """将月末特征与基本面数据合并。

    从 basic_panel 中提取每月末的 PB、总市值、PE_TTM 及季度 ROE，
    合并到 month_end_df 中供策略信号生成使用。
    """
    if basic_panel is None or basic_panel.empty:
        month_end_df["total_mv"] = np.nan
        month_end_df["pb"] = np.nan
        month_end_df["pe_ttm"] = np.nan
        month_end_df["roe"] = np.nan
        return month_end_df
    basic_panel = basic_panel.copy()
    basic_panel["month"] = basic_panel["date"].dt.to_period("M")
    month_basic = basic_panel.groupby(["code", "month"]).last().reset_index()
    # 选择需要合并的列（roe_fwd 可能不存在则忽略）
    merge_cols = ["code", "month", "total_mv", "pb", "pe_ttm"]
    for extra_col in ["roe_fwd"]:
        if extra_col in month_basic.columns:
            merge_cols.append(extra_col)
    merged = month_end_df.merge(month_basic[merge_cols], on=["code", "month"], how="left")
    # 统一命名：roe_fwd → roe
    if "roe_fwd" in merged.columns:
        merged["roe"] = merged["roe_fwd"]
        merged = merged.drop(columns=["roe_fwd"])
    else:
        merged["roe"] = np.nan
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
    panel[["open", "high", "low", "close", "adj_close", "volume", "amount"]] = (
        panel.groupby("code")[["open", "high", "low", "close", "adj_close", "volume", "amount"]].ffill()
    )
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
