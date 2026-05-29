# A 股策略回测

## 目录结构

- `backtest/`
  - `data_fetcher.py`：A 股日线数据、基准数据采集与预处理
  - `strategies.py`：52 周最高价、动量、反转、FF5 因子策略信号生成
  - `backtest_engine.py`：月度回测引擎与组合净值计算
  - `performance.py`：绩效指标计算
  - `visualization.py`：结果图表生成
  - `main.py`：主程序入口，生成 `results/report.md`

## 运行

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 运行主程序：

```bash
python backtest\main.py
```

3. 结果将在 `results/` 目录下生成：
- `net_value_curve.png`
- `rolling_sharpe.png`
- `heatmap_*.png`
- `report.md`

> 注意：本回测使用 `akshare` 数据接口，首次运行时会下载股票数据并缓存到 `data_cache/` 目录。