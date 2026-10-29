# LLM Finance Research

[![tests](https://github.com/Aisiweiyang/llm-finance-research/actions/workflows/tests.yml/badge.svg)](https://github.com/Aisiweiyang/llm-finance-research/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

面向大模型产业的金融实证研究工具包：API 定价、能力—价格前沿、发布/披露事件研究、财务现金流面板。提供明确的输入契约、样本排除记录、显式截距回归与可校验的运行产物。

**研究用途。这个版本提供方法和可运行示例，不发布已验证的投资策略，也不把历史探索结果当作已复现的论文结论。**

English: A small, portable empirical-research toolkit for LLM pricing, market-model event studies and SEC cash-flow panels. Offline examples are explicitly synthetic. Real datasets are supplied or retrieved separately; checksums establish integrity, not scientific validity.

## 快速开始

需要 Python 3.11 或以上。以下命令适用于 PowerShell，也可在其他系统使用相应的 Python 启动方式：

```powershell
git clone https://github.com/Aisiweiyang/llm-finance-research.git
cd llm-finance-research
python -m venv .venv
# Windows
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m llm_finance demo --output output/demo
.\.venv\Scripts\python.exe -m llm_finance verify output/demo --input-root output/demo/inputs
```

macOS / Linux 使用 `.venv/bin/python`。安装后也可以使用 `llm-finance` 命令。

演示完全离线，包含一组带人为冲击的合成行情和合成模型价格。输出事件 CAR、前沿表、回归表、诊断与 SHA-256 manifest；全部标记为 `SYNTHETIC_DEMO`。演示数据不代表真实市场或模型能力。

每次运行使用新的输出目录，已有结果不会被静默覆盖。完整命令见：

```powershell
python -m llm_finance --help
```

## 支持的研究流程

| 命令 | 输入 | 输出与范围 |
|---|---|---|
| `events` | 事件表、复权收盘价、显式市场模型配置 | CAR、预测误差标准差、逐事件拒绝原因 |
| `frontier` | 模型键、能力、同口径价格 | Pareto 前沿、无效样本记录、ln(price) |
| `ols` | 用户提供的分析表 | 带截距 OLS；HC1 或公司聚类标准误、样本损失 |
| `xbrl` | SEC companyfacts JSON、指定现金流标签 | 10-K 锚定的保守去累计化季度序列 |
| `fetch-sec` | 一个 CIK、真实 SEC User-Agent | 一个原始快照与来源/哈希回执 |
| `fetch-litellm` | 一个完整 Git 提交 SHA | 一个固定版本的价格 JSON 与来源回执 |
| `normalize-prices` | 本地 LiteLLM JSON、提交 SHA | 保留别名/版本键的每百万 token 价格 |
| `verify` | 一次运行目录，可选原始输入目录 | 输出库存和哈希检查；明确是否重验输入 |

### 事件研究

`prices.csv` 必须含 `date,ticker,adjusted_close`；`events.csv` 必须含 `event_id,event_date,ticker`。日期为所属市场的 `YYYY-MM-DD` 会话日期，事件代理关系由研究者核实。

```powershell
python -m llm_finance events --prices data/private/prices.csv --events data/private/events.csv --config templates/event_study.json --output output/events-v1
# 网安披露：必须使用结构化 items 字段；仅在正文提到关键词不会入样
python -m llm_finance events --prices data/private/prices.csv --events data/private/cyber_events.csv --item 1.05 --config templates/event_study.json --output output/cyber-v1
```

默认按 SPY 的交易会话对齐；其他市场必须修改 benchmark 并提供相应行情。事件日期晚于该日交易截止、时区差异、停牌、事件首次公开时间，需要在输入构造时解决。缺失证券会话不会被压缩掉：估计窗或事件窗存在缺失收益就拒绝该观测。

### 定价与面板回归

```powershell
python -m llm_finance frontier --input data/private/capability.csv --output output/frontier-v1
python -m llm_finance ols --input output/frontier-v1/frontier.csv --outcome ln_price --features ability open_weights --categorical vendor --output output/hedonic-v1
python -m llm_finance ols --input data/private/panel.csv --outcome revenue_growth --features capex_lag1 capex_lag2 --categorical firm quarter --cluster firm --output output/capex-v1
```

`capability.csv` 至少含 `model,ability,price`，价格为研究者固定输入/输出权重后的 USD/百万 token。不同指数版本、免费/批量/缓存价、路由别名不能无说明混合。两个回归示例中的额外列需由用户提供；工具不会伪造缺失特征或历史面板。

### 明确选择的网络采集

```powershell
# 设置为你自己的机构/项目与联系地址；不把环境变量提交 Git
$env:SEC_USER_AGENT = "Your Research Project your-contact@your-domain.org"
python -m llm_finance fetch-sec --cik 789019 --output data/raw/msft-companyfacts.json
python -m llm_finance xbrl --input data/raw/msft-companyfacts.json --tag PaymentsToAcquirePropertyPlantAndEquipment --unit USD --output output/msft-cashflow-v1
```

SEC 下载入口一次只请求一个公司，不批量爬取。LiteLLM 入口强制完整的 40 位提交 SHA，不能把 `main` 当作可复现版本。真实网络采集与离线方法验证分别记录。

## 目录与证据边界

```text
src/llm_finance/   方法、输入校验、显式采集与 CLI
templates/        可运行事件研究配置
data/catalog/     历史模型发布线索表；尚未重新逐条核验
tests/            离线数值核对、负面输入与命令行验证
docs/             方法、数据条件、历史问题与清理说明
.github/          多 Python 版本离线 CI
```

本项目独立于 Alice 量化系统运行，无 Alice 路径、账户内核或策略依赖。未来可以作为研究方法组件接入；目前未实现 Alice 集成。

- [方法与统计边界](docs/METHODS.md)
- [数据来源、许可与字段](docs/DATA_POLICY.md)
- [历史结果与修正状态](docs/RESEARCH_STATUS.md)
- [开源整理与删除清单](docs/RELEASE_NOTES.md)

## License

本仓库自有代码、说明与合成示例采用 [MIT](LICENSE)。第三方原始数据、模型能力指数、行情和供应商价格资料的权利不由本仓库许可证授予，详见数据政策。

