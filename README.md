# A股多策略量化回测框架

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![akshare](https://img.shields.io/badge/data-akshare-orange.svg)](https://github.com/akfamily/akshare)

一套基于沪深300成分股的**多策略量化回测系统**，系统性比较四种经典量化选股策略在A股市场的表现。回测周期覆盖 **2016年5月 — 2026年5月**（约10年），采用月度调仓、等权多空组合构建方式。

---

## 📊 核心结论

| 策略 | 年化收益率 | 夏普比率 | 最大回撤 |
|------|-----------|---------|---------|
| 🥇 **FF5简化三因子** | **14.06%** | **0.67** | -29.56% |
| 🥈 动量（6个月） | 13.20% | 0.51 | -42.50% |
| 🥉 52周最高价 | 2.67% | 0.16 | -61.02% |
| 反转策略（1个月） | -11.24% | -0.35 | -78.33% |
| *沪深300基准* | *4.29%* | *0.21* | *-39.92%* |

> **FF5简化三因子策略以年化14.06%、夏普0.67的表现全面领先，是A股市场中长期有效的量化策略。**

---

## 🧩 策略说明

本项目实现了四种经典学术策略，所有信号在 T 月末生成，T+1 月执行：

### 1. 52周最高价策略（52-Week High）
- **指标**：当前股价 / 过去52周最高价（Price-to-52W-High, PTH）
- **做多**：PTH 最高的前 10%（最接近52周高点的股票）
- **做空**：PTH 最低的后 10%
- **理论依据**：George & Hwang (2004), *Journal of Finance*

### 2. 动量策略（Momentum）
- **指标**：过去 6 个月累计收益（跳过最近 1 个月，避免短期反转效应）
- **做多**：动量最强的 前 10%
- **做空**：动量最弱的后 10%
- **理论依据**：Jegadeesh & Titman (1993), *Journal of Finance*

### 3. 反转策略（Reversal）
- **指标**：过去 1 个月收益
- **做多**：跌幅最大的后 10%（"输家"组合，押注反弹）
- **做空**：涨幅最大的前 10%
- **理论依据**：Jegadeesh (1990), *Journal of Finance*

### 4. FF5简化三因子策略（Fama-French Five-Factor，简化版）
- **价值因子（BM）**：1 / PB，越高越好
- **盈利因子（Profitability）**：ROE（优先）或 1/PE_TTM
- **投资因子（Investment）**：过去 12 个月市值增长率，越低越好
- **综合评分**：三因子等权排名加总，做多前30%、做空后30%
- **说明**：因数据限制，暂缺规模因子（SMB）与独立市场因子，使用代理变量代替 FF5 原文变量

---

## 🗂️ 项目结构

```
.
├── backtest/                    # 核心回测引擎
│   ├── main.py                  # 🚀 主入口：编排完整回测流程
│   ├── data_fetcher.py          # 📡 数据获取与特征工程
│   │                            #    - 沪深300成分股筛选
│   │                            #    - 日线行情下载与缓存（后复权）
│   │                            #    - 基本面数据（PB、市值、ROE）
│   │                            #    - 数据清洗与缺失处理
│   │                            #    - 特征计算（PTH、动量、PE_TTM等）
│   ├── strategies.py            # 🧠 四种策略信号生成
│   ├── backtest_engine.py       # ⚙️ 投资组合构建与净值计算
│   ├── performance.py           # 📈 绩效指标（夏普、回撤、胜率等）
│   └── visualization.py         # 🎨 可视化（净值曲线、热力图、滚动夏普）
├── data_cache/                  # 💾 560只股票日线数据缓存
├── results/                     # 📊 输出结果
│   ├── report.md                #    完整回测报告
│   ├── net_value_curve.png      #    净值曲线
│   ├── rolling_sharpe.png       #    滚动12月夏普比率
│   ├── heatmap_*.png            #    月/10日收益热力图
│   └── daily_returns_3y.*       #    近三年日度收益对比
└── requirements.txt             # Python 依赖
```

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- 建议使用虚拟环境

### 安装

```bash
git clone https://github.com/your-username/a-share-quant-backtest.git
cd a-share-quant-backtest
pip install -r requirements.txt
```

### 运行

```bash
python backtest/main.py
```

> ⏳ **注意**：首次运行会通过 `akshare` 下载约 **31.5 GB** 的股票日线数据并缓存至 `data_cache/` 目录，耗时约 30-60 分钟。后续运行直接读取缓存，无需重新下载。

### 输出

运行完成后，`results/` 目录将生成：

- `report.md` — 完整的中文回测报告（含绩效表格与分析）
- `net_value_curve.png` — 四策略 + 基准的净值曲线
- `rolling_sharpe.png` — 12 个月滚动夏普比率对比
- `heatmap_*.png` — 各策略月度 / 每 10 日收益热力图
- `daily_returns_3y.csv / .png` — 近三年日度累计收益

---

## 📈 数据说明

| 项目 | 说明 |
|------|------|
| **股票池** | 沪深300成分股（经过数据质量过滤后约 **108只**） |
| **数据源** | [akshare](https://github.com/akfamily/akshare)（同花顺 / 百度估值接口） |
| **行情数据** | 日线后复权（OHLCV），2016年起 |
| **基本面** | PB（市净率）、总市值、季度ROE、EPS、净利润 |
| **基准** | 沪深300指数（000300.SH） |
| **调仓频率** | 月度（月末生成信号，次月执行） |
| **持仓方式** | 等权多空（long-short equal-weighted） |

### 数据清洗规则
- 剔除缺失率 > 20% 的股票（上市不足 10 年或长期停牌）
- 剔除连续缺失 > 5 个交易日的区段
- 对剩余缺失进行前向填充（forward fill）

---

## ⚠️ 已知局限

当前版本的回测为学术研究框架，存在以下简化：

- **无行业中性化**：未对行业偏离进行控制，策略可能存在行业集中风险
- **等权配置**：未使用波动率倒数加权或风险平价等优化方法
- **FF5 为简化版**：使用代理变量替代 Fama-French 原文变量，缺少 SMB 因子
- **忽略交易成本**：假设零手续费、零滑点，实际交易中存在冲击成本
- **仅限沪深300**：结论外推至中证500、中证1000等池可能不同
- **未考虑停牌/涨跌停**：实际交易中停牌和涨跌停板可能影响调仓执行

---

## 🔮 改进方向

- [ ] 引入行业中性化处理（申万一级行业分类）
- [ ] 实现波动率倒数加权 / 风险平价
- [ ] 完善 FF5 因子（加入 SMB 和独立 RMW、CMA、INV 计算）
- [ ] 加入交易成本模型（佣金 + 印花税 + 滑点）
- [ ] 扩展至中证500 / 中证1000 股票池
- [ ] 增加参数敏感性分析（分位数阈值、调仓频率等）
- [ ] 蒙特卡洛模拟评估策略稳定性

---

## 📚 参考文献

1. George, T. J., & Hwang, C. Y. (2004). The 52-week high and momentum investing. *Journal of Finance*, 59(5), 2145-2176.
2. Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. *Journal of Finance*, 48(1), 65-91.
3. Jegadeesh, N. (1990). Evidence of predictable behavior of security returns. *Journal of Finance*, 45(3), 881-898.
4. Fama, E. F., & French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial Economics*, 116(1), 1-22.

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

*项目为《金融数学概论》期末项目。欢迎提出 Issue 和 Pull Request。*
