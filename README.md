# LLM-Finance-Research · LLM 金融实证研究

**作者与维护者：[Aisiweiyang](https://github.com/Aisiweiyang)**

[![tests](https://github.com/Aisiweiyang/LLM-Finance-Research/actions/workflows/tests.yml/badge.svg)](https://github.com/Aisiweiyang/LLM-Finance-Research/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

这个项目用 Python 研究大模型的 API 价格、模型发布后的股票市场反应，以及相关公司的财务数据。

目前整理了事件研究、能力与价格比较、面板回归、SEC 现金流数据处理几部分代码。可以用自己的数据运行，也可以先跑仓库里的离线示例。

示例使用合成数据。真实行情和模型评测数据需要另行准备，旧项目的探索结果没有作为本版研究结论发布。

Python code for studying LLM API prices, model releases and company financial data.

## 快速开始

需要 Python 3.11 或以上。以下命令适用于 PowerShell，也可在其他系统使用相应的 Python 启动方式：

```powershell
git clone https://github.com/Aisiweiyang/LLM-Finance-Research.git
cd LLM-Finance-Research
python -m venv .venv
# Windows
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m llm_finance demo --output output/demo
.\.venv\Scripts\python.exe -m llm_finance verify output/demo --input-root output/demo/inputs
```

macOS / Linux 使用 `.venv/bin/python`。安装后也可以使用 `llm-finance` 命令。

示例会生成合成行情和模型价格，计算 CAR、价格前沿和回归表。结果保存在 output/demo，标记为 `SYNTHETIC_DEMO`。

每次运行需要换一个输出目录，避免覆盖旧结果。查看全部命令：

```powershell
python -m llm_finance --help
```

## 功能

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

`capability.csv` 至少含 `model,ability,price`，价格单位为 USD/百万 token。输入与输出 token 的混合权重、能力指数版本和价格类型需要保持一致。回归示例里的 open_weights、vendor 和滞后变量等列需要自行准备。

### 下载数据

```powershell
# 设置为你自己的机构/项目与联系地址；不把环境变量提交 Git
$env:SEC_USER_AGENT = "Your Research Project your-contact@your-domain.org"
python -m llm_finance fetch-sec --cik 789019 --output data/raw/msft-companyfacts.json
python -m llm_finance xbrl --input data/raw/msft-companyfacts.json --tag PaymentsToAcquirePropertyPlantAndEquipment --unit USD --output output/msft-cashflow-v1
```

SEC 命令每次下载一家公司的数据。LiteLLM 下载需要完整的 40 位提交 SHA，方便以后取得同一版本的价格文件。

## 目录

```text
src/llm_finance/   方法、输入校验、显式采集与 CLI
templates/        可运行事件研究配置
data/catalog/     历史模型发布线索表；尚未重新逐条核验
tests/            离线数值核对、负面输入与命令行验证
docs/             方法、数据条件、历史问题与清理说明
.github/          多 Python 版本离线 CI
```

代码可独立运行，不依赖 Alice 量化系统。

- [计算方法与限制](docs/METHODS.md)
- [数据来源、许可与字段](docs/DATA_POLICY.md)
- [历史结果与修正状态](docs/RESEARCH_STATUS.md)
- [开源整理与删除清单](docs/RELEASE_NOTES.md)

## License

代码和合成示例采用 [MIT](LICENSE) 许可证。第三方数据的使用条件见[数据说明](docs/DATA_POLICY.md)。

