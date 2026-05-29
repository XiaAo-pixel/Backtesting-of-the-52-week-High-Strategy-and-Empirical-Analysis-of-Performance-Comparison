import os
import sys
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backtest import backtest_engine, data_fetcher, performance, strategies, visualization


DATA_DIR = "data_cache"
RESULTS_DIR = "results"
START_DATE = "2016-05-01"
END_DATE = "2026-05-01"
BENCHMARK_CODE = "000300.SH"
TOP_N = 300


def ensure_folders():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)


def generate_report(report_path: str, stats: pd.DataFrame, analysis: str, image_paths: dict, data_info: dict):
    # 新增参数 stats_3y（近三年绩效表）可传入为 DataFrame，否则仅输出全部期间的 stats
    # 为兼容旧调用，允许传入 None
    stats_3y = data_info.get("stats_3y") if data_info is not None else None
    lines = [
        "# A股策略回测报告",
        "",
        "## 数据说明",
        f"- 股票池：沪深300成分股前 {data_info['stock_count']} 只（按成分股顺序选取）。",
        f"- 时间区间：{data_info['start_date']} 至 {data_info['end_date']}。",
        f"- 数据来源：akshare（A股日线数据、基础财务数据）。",
        "",
        "## 回测结果摘要",
        "",
        "策略绩效指标（全部期间）：",
        "",
        stats.to_markdown(index=False, floatfmt=".4f"),
        "",
    ]

    if stats_3y is not None:
        lines.extend([
            "## 近三年策略绩效（滚动/截断至最近 3 年）：",
            "",
            stats_3y.to_markdown(index=False, floatfmt=".4f"),
            "",
        ])

    lines.extend([
        "## 策略表现分析",
        analysis,
        "",
        "## 图表展示",
    ])
    for caption, path in image_paths.items():
        lines.append(f"### {caption}")
        lines.append(f"![]({path})")
        lines.append("")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ensure_folders()
    print("开始回测：读取股票池和数据")
    symbols = data_fetcher.get_hs300_stocks(top_n=TOP_N)
    raw_panel = data_fetcher.build_price_panel(symbols, START_DATE, END_DATE, cache_dir=DATA_DIR)
    print(f"已获取 {len(raw_panel['code'].unique())} 只股票的日线数据")

    panel = data_fetcher.standardize_panel(raw_panel, START_DATE, END_DATE)
    panel = data_fetcher.exclude_low_frequency(panel, max_missing_ratio=0.2)
    panel = data_fetcher.drop_long_missing_segments(panel, max_gap=5)
    panel = data_fetcher.fill_forward_panel(panel)
    panel = data_fetcher.compute_features(panel)
    monthly_returns = data_fetcher.compute_monthly_returns(panel)
    month_end_features = data_fetcher.get_month_end_features(panel)

    print("获取财务基础因子数据")
    basic_panel = data_fetcher.build_basic_panel(symbols, START_DATE, END_DATE, cache_dir=DATA_DIR)
    month_end_features = data_fetcher.merge_month_end_fundamentals(month_end_features, basic_panel)

    print("获取基准数据")
    benchmark = data_fetcher.fetch_benchmark(BENCHMARK_CODE, START_DATE, END_DATE)
    benchmark_monthly = data_fetcher.calculate_benchmark_returns(benchmark)

    print("生成策略信号")
    signal_52wh = strategies.generate_52wh_signal(month_end_features)
    signal_mom = strategies.generate_mom_signal(month_end_features)
    signal_rev = strategies.generate_rev_signal(month_end_features)
    signal_ff5 = strategies.generate_ff5_signal(month_end_features)

    print("运行回测引擎")
    results = {
        "52 周最高价策略": backtest_engine.run_backtest("52 周最高价策略", signal_52wh, monthly_returns, panel),
        "动量策略": backtest_engine.run_backtest("动量策略", signal_mom, monthly_returns, panel),
        "反转策略": backtest_engine.run_backtest("反转策略", signal_rev, monthly_returns, panel),
        "FF5 因子策略": backtest_engine.run_backtest("FF5 因子策略", signal_ff5, monthly_returns, panel),
    }

    print("计算绩效指标")
    metrics = performance.performance_table({
        k: v for k, v in results.items()
    }, benchmark_monthly["return"])
    metrics[["年化收益率", "年化波动率", "夏普比率", "最大回撤", "月度胜率"]]

    # 计算近三年绩效表（基于 monthly 数据截断到最近 3 年）
    try:
        last_month = max([data["monthly"]["month"].max() for data in results.values()])
        start_3y_month = pd.to_datetime(last_month) - pd.DateOffset(years=3)
        filtered_results = {}
        for name, data in results.items():
            monthly = data["monthly"]
            monthly_f = monthly[monthly["month"] >= start_3y_month].copy()
            # 重新基准化近三年月度净值（期初 NAV=1），避免使用全样本累计 NAV 导致的偏差
            if not monthly_f.empty:
                monthly_f = monthly_f.reset_index(drop=True)
                monthly_f["nav"] = (1 + monthly_f["strategy_return"]).cumprod()
            filtered_results[name] = {"monthly": monthly_f, "daily": data.get("daily", pd.DataFrame())}
        benchmark_3y = benchmark_monthly[benchmark_monthly["month"] >= start_3y_month]
        metrics_3y = performance.performance_table(filtered_results, benchmark_3y["return"]) if not benchmark_3y.empty else None
    except Exception:
        metrics_3y = None

    print("绘制图表")
    nav_dict = {name: data["monthly"][["month", "nav"]].assign(date=data["monthly"]["month"].dt.to_timestamp()) for name, data in results.items()}
    nav_dict["沪深300基准"] = benchmark_monthly.assign(nav=(1 + benchmark_monthly["return"]).cumprod()).assign(date=benchmark_monthly["month"].dt.to_timestamp())
    nav_file = os.path.join(RESULTS_DIR, "net_value_curve.png")
    visualization.plot_nav_curves(nav_dict, nav_file, "策略净值曲线与沪深300基准")

    heatmap_images = {}
    for name, data in results.items():
        file_path = os.path.join(RESULTS_DIR, f"heatmap_{name}.png")
        visualization.plot_monthly_heatmap(data["monthly"].assign(month=data["monthly"]["month"].dt.to_timestamp()), file_path, f"{name} 月度收益热力图")
        heatmap_images[name] = file_path

    print("绘制每10交易日收益热力图")
    ten_day_heatmaps = {}
    for name, data in results.items():
        series = data["daily"].set_index("date")["daily_return"].copy()
        file_path = os.path.join(RESULTS_DIR, f"heatmap_10d_{name}.png")
        visualization.plot_10d_return_heatmap(series, file_path, f"{name} 每10交易日收益热力图", years=3)
        ten_day_heatmaps[name] = file_path

    print("绘制滚动夏普比")
    rolling_dict = {}
    for name, data in results.items():
        # 使用 month 作为索引，确保返回的 Series 有时间索引
        try:
            ser = data["monthly"].set_index("month")["strategy_return"]
        except Exception:
            ser = data["monthly"]["strategy_return"]
        rolling_dict[name] = performance.rolling_sharpe(ser, window=12)
    rolling_file = os.path.join(RESULTS_DIR, "rolling_sharpe.png")
    visualization.plot_rolling_sharpe(rolling_dict, rolling_file, "策略滚动 12 个月夏普比")

    # 生成近三年日度收益比较并导出CSV
    print("生成近三年日度收益比较")
    # 选择最近可用日期的前三年时间窗口
    last_date = max([data["daily"]["date"].max() for data in results.values()])
    start_3y = (pd.to_datetime(last_date) - pd.DateOffset(years=3)).date()
    daily_returns = []
    for name, data in results.items():
        df = data["daily"][["date", "daily_return"]].copy()
        df = df[(df["date"] >= pd.to_datetime(start_3y))]
        df = df.set_index("date").rename(columns={"daily_return": name})
        daily_returns.append(df[name])
    # 合并为一个 DataFrame
    daily_df = pd.concat(daily_returns, axis=1).fillna(0)
    csv_path = os.path.join(RESULTS_DIR, "daily_returns_3y.csv")
    daily_df.to_csv(csv_path, index=True)
    # 绘图
    recent_plot = os.path.join(RESULTS_DIR, "daily_returns_3y.png")
    visualization.plot_recent_3y_daily_returns(daily_df, recent_plot, "近三年日度累计收益比较")

    print("生成报告")
    analysis = (
        "本次回测采用沪深300前 200 只成分股，时间区间为 2016-05-01 至 2026-05-01。"
        "52 周最高价策略、动量策略、反转策略和 FF5 因子策略均使用月度调仓、等权多空组合。"
        "由于数据接口可用性限制，FF5 因子策略的价值、盈利、投资因子使用市净率、估值反转和市值增长的简化代理进行构建。"
        "回测结果请参考绩效指标表和图表。"
    )
    report_path = os.path.join(RESULTS_DIR, "report.md")
    all_images = {
        "策略净值曲线": nav_file,
        "滚动夏普比": rolling_file,
    }
    all_images.update({f"{name} 月度收益热力图": path for name, path in heatmap_images.items()})
    all_images.update({f"{name} 每10交易日收益热力图": path for name, path in ten_day_heatmaps.items()})
    data_info = {
        "stock_count": len(panel["code"].unique()),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "stats_3y": metrics_3y,
    }
    generate_report(report_path, metrics, analysis, all_images, data_info)

    print(f"回测完成，结果保存至 {RESULTS_DIR}，报告文件：{report_path}")


if __name__ == "__main__":
    main()
