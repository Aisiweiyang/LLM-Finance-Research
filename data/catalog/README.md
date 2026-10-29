# 历史发布事件线索 / Historical release-event leads

release_events.csv 保留原项目26个发布事件的来源线索，以及研究者当时使用的证券代理。

- 日期与映射未在本次重新核验。
- proxy_tickers_json 为 JSON 数组，读取时使用 json.loads。
- source_status 全部为 HISTORICAL_CATALOG_NOT_REVALIDATED。
- 它不是已准入的交易事件表，也不包含行情和能力指数。
- 正式事件输入须按代理展开成 event_id,event_date,ticker，并核实源链接、首次公开时间、时区和交易会话。

The catalog contains historical research leads, not verified current mappings or
PIT-certified event dates. No market price data is redistributed here.
