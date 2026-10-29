# 数据来源、许可与字段

## 发布内容

公开仓库包含自有方法代码、合成示例生成器、输入规范及一份历史模型发布线索目录。不分发原始市场行情、8-K 全文、OpenRouter/Hugging Face/Artificial Analysis 响应或大体积价格历史缓存。

MIT 许可证仅覆盖本仓库有权许可的内容，不代替第三方数据使用和再分发条件。使用者需要独立核验数据的授权、口径与采集条件。

| 来源 | 入口 | 本仓库的处理 |
|---|---|---|
| LiteLLM 版本化价格文件 | [原文件](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)、[上游许可证](https://github.com/BerriAI/litellm/blob/main/LICENSE) | 显式指定 commit 下载；不提交原始快照；别名与日期版本键分别保留 |
| SEC companyfacts | [官方 API 说明](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | 一次下载一个公司；真实标识 User-Agent；原始响应与哈希回执保存在本地 |
| SEC 披露项目号 | [SEC 开发资源](https://www.sec.gov/about/developer-resources) | 对输入的结构化 items 做精确成员筛选；关键词命中不充当项目号 |
| 市场价格与基准 | 用户合法取得的复权收盘价 | 不打包再分发行情；记录复权、时区、日历和来源 |
| 能力指数/供应商报价 | 用户取得并核验的同版本表 | 不宣称具有第三方评测数据的再许可权 |

SEC 请求应遵守其 [开发资源与 Fair Access](https://www.sec.gov/about/developer-resources)。当前入口不进行全量枚举；批处理由用户另行控制频率，不能通过并发机器规避服务端限制。

## 输入契约

### 事件研究价格表

- date：所属市场交易会话日期，YYYY-MM-DD。
- ticker：证券标识，字符串；date/ticker 组合唯一。
- adjusted_close：有限、正的复权收盘价，来自同一口径。
- 必须提供完整基准日历。对资产缺失会话不前填价格、不压缩日期。

### 事件表

- event_id、ticker：组合唯一；一个事件多个代理用多行表示。
- event_date：已核实的市场事件会话日期。请另行保存首次公开时间与日期处理证据。
- items：仅 SEC 筛选需要，接受分号/逗号分隔项目号；1.05 与 1.050 不等同。
- source_url、available_at、代理映射证据等应在原表保留。工具不会把抓取时间写成历史可得时间。

### 能力价格表

- model：唯一、非空的具体模型或路由键。
- ability：固定版本指数或测量值。
- price：研究者固定 token 混合口径后的 USD/百万 token。
- open_weights、vendor 等回归特征需额外提供；数值特征不得含任意文本。

## 历史线索目录

data/catalog/release_events.csv 来源于本项目旧版手工研究目录。它保留研究者当时记录的事件与公开来源链接，所有行标记 HISTORICAL_CATALOG_NOT_REVALIDATED。本次未重新逐条访问来源，不把旧 verify 字段转换为当前认证。日期、代理关系、盘后时点和发布阶段需重新核实后才能进入正式分析。

## 来源回执

下载返回 HTTP 成功后保存原始字节、URL、实际抓取时刻与 SHA-256。实时接口可能修订，下载成功不等于历史时点可得性通过；回执始终保留 historical_availability_certified=false。

