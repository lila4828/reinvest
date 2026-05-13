# CrewAI Migration Plan

This document records the current CrewAI responsibilities before replacing them step by step. It is a planning document only. It does not propose changing runtime code in this step.

## 1. Current Architecture Summary

The current system is a hybrid LangGraph + CrewAI report generation pipeline.

- FastAPI starts report generation through `backend/api.py`.
- `backend/pipelines/report_pipeline.py` is the API-facing pipeline entrypoint and delegates to `main.run_financial_crew()`.
- `backend/main.py` still creates CrewAI LLMs, Agents, and Task factories through `create_llms()` and `create_crew_components()`.
- LangGraph owns orchestration in `backend/graphs/report_graph.py`.
- `ReportState` in `backend/schemas/report_state.py` owns runtime state shared between graph nodes.
- CrewAI Agent/Task objects still perform the analysis work inside Macro, Accounting, Research, Youtube RAG, and final Analysis.
- `save_pipeline_output()` persists generated markdown and summary output through `services/report_file_service.py`.
- The frontend follows job progress by polling `/api/report-status/{job_id}`. `status_callback` updates backend `targets_status` so the UI can show stock-level progress.

## 2. Current LangGraph vs CrewAI Responsibility Split

### LangGraph Controls

- Node ordering: `validate_input -> macro -> accounting -> research -> youtube_rag -> price -> analysis -> save_summary -> finalize`.
- Per-stock execution through `run_single_report_graph()`.
- Conditional failure routing through `should_continue()`.
- Runtime state mutation on each node.
- Status notification hooks through `with_status_updates()` and `notify_status()`.
- Cleanup of runtime-only fields such as `agents`, `tasks`, `status_callback`, `research_result`, and `youtube_result`.

### CrewAI Still Controls

- Macro data collection task execution.
- Accounting data collection task execution.
- Research/news collection task execution.
- Youtube RAG synthesis task execution.
- Final investment report writing task execution.

### Connection Files

- `backend/pipelines/report_pipeline.py`: API-facing wrapper that calls `main.run_financial_crew()`.
- `backend/main.py`: creates CrewAI Agents/Tasks and exposes step functions called by graph nodes.
- `backend/graphs/report_graph.py`: graph nodes import and call `main.py` step functions.
- `backend/schemas/report_state.py`: shared state contract.

### Key ReportState Fields

- Identity/status: `ticker`, `company_name`, `status`, `current_step`, `errors`.
- Runtime dependencies: `agents`, `tasks`, `status_callback`.
- Macro: `macro_context`, `macro_data`, `macro_json`, `macro_score`, `macro_score_reasons`.
- Accounting/price: `accounting_data`, `acc_data`, `price_data`, `current_price`, `target_buy_price`, `defense_price`.
- Research/Youtube: `research_result`, `research_data`, `youtube_result`, `youtube_context`.
- Report output: `final_report`, `markdown_report`, `output_report`, `chart_data`.
- Persistence: `result_dir`, `report_file_path`, `summary_header`, `summary_saved`, `summary_deferred`.

### status_callback and targets_status

`status_callback` is stored in state while the graph is running. Each node wrapper updates `current_step`, calls `status_callback(state)`, runs the node, then calls it again. `backend/api.py` uses this callback to update the job store's optional `targets_status` list. The frontend polls `/api/report-status/{job_id}` and uses `targets_status` to display per-stock progress.

## 3. Macro Step Analysis

### Current Agent Role

`flows/macro/agent.py` defines `MacroAgent.macro_economist()`. It is a data mapping agent. Its job is to call `fetch_macro_data` and map returned macro JSON into `MacroOutput` without inventing or recalculating values.

### Current Task Role

`flows/macro/task.py` defines `MacroTask.analyze_macro_economy()`. It instructs the agent to use the macro API tool and return structured `MacroOutput`.

### Input Values

- `macro_agent`
- `macro_tasks`
- Optional `ReportState`
- Tool output from `fetch_macro_data`

### Output Values

`run_macro_step()` returns:

- `macro_score`
- `macro_score_reasons`
- `macro_json`

It also writes `state["macro_data"]` with raw macro data, JSON, score, and score reasons.

### Tools Used

- `flows.macro.tool.fetch_macro_data`

### Pydantic / Output Shape

`MacroOutput` fields include:

- `exchange_rate`
- `us_10y_yield`
- `nasdaq_index`
- `wti_price`
- `vix_index`
- one-month change fields
- `risk_warnings`
- `macro_briefing`
- `is_data_valid`
- `error`

### Fallback/Error Handling

If `macro_result.pydantic` is missing or `is_data_valid` is false, the step creates neutral macro data:

- `macro_score = 0`
- reason: neutral score applied
- macro fields mostly `None`
- `is_data_valid = False`

### macro_json, macro_score, macro_score_reasons

When valid, `macro_json` is `MacroOutput.model_dump_json(indent=2)`. `macro_score` and reasons are calculated in Python by `calculate_macro_score()` using exchange rate, US 10Y yield, and VIX. The CrewAI task does not own scoring.

### Batch-Level Macro Execution

`run_multiple_report_pipeline()` receives a `macro_context`. If none is provided, it calls `build_macro_context()`, which runs macro once before iterating stocks. This is the batch-level macro execution path.

### Macro Injection into Each Stock Graph

`run_single_report_graph()` initializes each stock state with:

- `macro_context`
- `macro_data`
- `macro_json`
- `macro_score`
- `macro_score_reasons`

The graph `macro_node()` detects pre-existing macro values and passes through without rerunning macro per stock.

### Direct-Function Replacement Proposal

Replace `MacroAgent` and `MacroTask` with a direct Python function:

1. Call `fetch_macro_data` directly.
2. Validate and normalize the returned dict against the same `MacroOutput` schema or an equivalent lightweight dataclass.
3. Preserve fallback neutral macro behavior.
4. Keep `calculate_macro_score()` unchanged.
5. Return the same `(macro_score, macro_score_reasons, macro_json)` tuple.

### Risks

- Macro running once per stock instead of once per batch.
- Different null/default handling changing frontend macro display.
- `macro_json` format changes breaking summary `MACRO_DATA`.
- Missing `macro_score` causing final opinion calculation failure.

## 4. Accounting Step Analysis

### Current Agent Role

`flows/accounting/agent.py` defines `AccountingAgent.financial_analyst()`. It calls `fetch_financial_data` and maps the tool result into `AccountingOutput`.

### Current Task Role

`flows/accounting/task.py` defines `AccountingTask.analyze_financial_statements()`. It asks the agent to fetch a specific company's financial data and preserve returned JSON values without making PASS/FAIL decisions.

### Input Values

- `accounting_agent`
- `acc_tasks`
- `ticker`
- `company`
- Optional `ReportState`
- Tool output from `fetch_financial_data`

### Output Values

`run_accounting_step()` returns:

- `acc_data`
- `failed_report_item`

On success, `failed_report_item` is `None`. On failure, `acc_data` is `None` and `failed_report_item` is a report item with status `FAILED`.

### Tools Used

- `flows.accounting.tool.fetch_financial_data`

### Pydantic / Output Shape

`AccountingOutput` includes:

- ticker and current price
- PER/PBR/dividend yield
- moving averages: `ma_60`, `ma_200`, `ma_350`, `ma_500`, `ma_999`
- ROE fields
- arrays: `revenue`, `net_income`, `fcf`
- debt, operating margin, sector, industry
- financial summary
- `is_data_valid`
- `error`

### Fallback/Error Handling

The step fails the stock if:

- pydantic output is missing or invalid
- numeric series are missing/invalid
- three-year net income is all negative
- three-year FCF is all negative
- latest revenue is zero or below
- debt-to-equity is over 200

Failure returns `build_failed_report_item()` and marks the stock state failed. This failure is isolated to that stock by `run_multiple_report_pipeline()`.

### acc_data, Price Targets, Scores, chart_data

- `acc_data` is `AccountingOutput.model_dump(mode="json")`.
- `fundamental_score` and reasons are added by `calculate_fundamental_score()`.
- `current_price`, `target_buy_price`, and `defense_price` are calculated later in `run_price_step()` using `calculate_price_targets()`.
- `chart_data` is not produced by accounting directly. It is expected to be produced in the final `AnalysisOutput` from the accounting arrays, then preserved in markdown JSON and state.

### Direct-Function Replacement Proposal

Replace CrewAI with:

1. Direct `fetch_financial_data(ticker)` call.
2. Validate with `AccountingOutput` or a dedicated parser.
3. Keep existing Python PASS/FAIL rules unchanged.
4. Keep `calculate_fundamental_score()` and `calculate_price_targets()` unchanged.
5. Return the same `(acc_data, failed_report_item)` contract.

### Risks

- Incorrect array order for revenue/net income/FCF.
- Losing PASS/FAIL isolation per stock.
- Missing fields used by `run_price_step()` or final analysis.
- Different failure messages changing summary/debug expectations.
- Broken `chart_data` if analysis replacement later does not map arrays correctly.

## 5. Research Step Analysis

### Current Agent Role

`flows/research/agent.py` defines `ResearchAgent.news_researcher()`. It uses `search_tool` and summarizes real search results into structured research sentiment.

### Current Task Role

`flows/research/task.py` defines `ResearchTask.collect_news_task()`. It requires searches for latest news, price/supply-demand/investor sentiment, earnings/reports, industry issues, and English stock news.

### Input Values

- `researcher_agent`
- `res_tasks`
- `company`
- Optional `ReportState`
- Results from `safe_serper_news_search` through `search_tool`

### Output Values

`run_research_step()` returns a CrewAI result. `parse_research_result()` converts that to:

- `sentiment`: `1`, `0`, or `-1`
- `research_json`

It writes `state["research_data"]` with raw data, JSON, and sentiment.

### Tools Used

- `flows.research.tool.search_tool`
- The task text requires `safe_serper_news_search`.

### Pydantic / Output Shape

`ResearchOutput` includes:

- `sentiment_score`
- `momentum_strength`
- `news_summary`
- `is_data_valid`

### Fallback/Error Handling

`run_research_step()` catches CrewAI/search errors and returns `DummyResult()`. `parse_research_result()` treats missing/invalid pydantic data as neutral:

- sentiment score 50
- momentum `LOW`
- invalid flag false
- final `sentiment = 0`

### No Valid News Results

The task requires `is_data_valid=False`, `sentiment_score=50.0`, `momentum_strength=LOW`, and a no-news summary if no valid real news exists. The parser then treats this as neutral.

### Direct-Function Replacement Proposal

Replace CrewAI with:

1. Direct calls to existing search logic such as `safe_serper_news_search`.
2. Deterministic filtering of invalid/stale/irrelevant results.
3. Optional OpenAI structured-output call to summarize the filtered result list into `ResearchOutput`.
4. Preserve neutral fallback when no valid results exist.

### Risks

- Search calls during tests if not stubbed.
- Fabricated news summaries if raw result validation is weakened.
- Sentiment thresholds changing final opinion.
- Long or malformed JSON breaking final analysis input compaction.

## 6. Youtube RAG Step Analysis

### Current Agent Role

`flows/youtube/agent.py` defines `YoutubeAgent.guru_analyst()`. It uses a local YouTube search tool and maps retrieved transcript context into `YoutubeOutput`.

### Current Task Role

`flows/youtube/task.py` defines `YoutubeTask.extract_guru_view()`. It asks the agent to search local YouTube transcript data for a company and classify the result as `SPECIFIC`, `MARKET`, `MINDSET`, `RISK`, `PSYCHOLOGY`, or `N/A`.

### Input Values

- `youtube_agent`
- `yt_tasks`
- `company`
- Optional `ReportState`
- Local Chroma/vector search results from the YouTube tool

### Output Values

`run_youtube_rag_step()` returns a CrewAI result. `parse_youtube_result()` converts that to:

- `guru_score`
- `guru_weight`
- `youtube_json`

It writes `state["youtube_context"]`.

### Tools Used

- `flows.youtube.tool.get_guru_youtube_tool()`
- Tool name in prompts: `local_youtube_search_tool`
- Underlying local YouTube RAG/Chroma search

### Pydantic / Output Shape

`YoutubeOutput` includes:

- `guru_sentiment_score`
- `key_strategy`
- `content_type`
- `insight_date`
- `freshness_level`
- `mindset_summary`
- `market_principle`
- `risk_control`
- `guru_insight_details`
- `is_data_valid`

### Fallback/Error Handling

`run_youtube_rag_step()` catches exceptions and returns `DummyResult()`. `parse_youtube_result()` treats invalid/missing pydantic as neutral:

- `guru_sentiment_score = 50.0`
- `content_type = N/A`
- `is_data_valid = False`
- `guru_weight = 0.0`

Valid output only gets final-score weight when `content_type == SPECIFIC`, freshness is `FRESH` or `RECENT`, and guru score is not neutral.

### Live/Upcoming/Pending Video Logic

The YouTube update guard and pending live video logic must remain untouched during CrewAI removal. It is outside the Agent/Task replacement boundary. It protects report generation from blocking on live/upcoming videos, downloads, Whisper, and vector rebuilds.

### Direct-Function Replacement Proposal

Replace CrewAI with:

1. Direct call to the existing local YouTube search tool or its underlying search function.
2. Keep Chroma integration unchanged until CrewAI and `crewai-tools` are fully removed.
3. Validate selected docs.
4. Optionally call OpenAI structured output to map retrieved docs into `YoutubeOutput`.
5. Preserve neutral fallback and guru weighting rules.

### Risks

- Accidentally running YouTube update/download/Whisper during tests.
- Chroma/CrewAI dependency conflict if `langchain_chroma` migration happens too early.
- Content-type classification changes affecting guru weight.
- Stale transcript handling changing investment conclusions.

## 7. Analysis Step Analysis

### Current Agent Role

`flows/analysis/agent.py` defines `AnalysisAgent.investment_analyst()`. It writes the final structured report JSON from already-computed inputs. It must not change system-derived final opinion or price guidance.

### Current Task Role

`flows/analysis/task.py` defines `AnalysisTask.report_writing_task()`. It receives compacted accounting, macro, research, YouTube, final opinion, target buy price, and defense price. It instructs the agent to produce `AnalysisOutput`.

### Input Values

- `analyst_agent`
- `ana_tasks`
- `company`
- `acc_data`
- `macro_json`
- `research_json`
- `youtube_json`
- `final_opinion`
- `target_buy_price`
- `defense_price`
- Optional `ReportState`

### Output Values

`run_final_analysis_step()` returns a CrewAI result. If it has `pydantic`, `render_markdown_report()` creates markdown and state output.

### Pydantic / Output Shape

`AnalysisOutput` includes:

- `investment_opinion`
- `one_line_conclusion`
- `executive_summary`
- `macro_analysis`
- `fundamental_analysis`
- `momentum_analysis`
- `guru_analysis`
- `final_conclusion`
- `chart_data`, an array of `ChartData`

`ChartData` includes:

- `period`
- `revenue`
- `net_profit`
- `fcf`

### Fallback/Error Handling

If pydantic output is missing, graph logic creates a failed fallback report from raw output, marks status failed, and records an error. Exceptions also create a failed state and output report.

### Final report_data Creation

`render_markdown_report()` reads `final_result.pydantic` and renders:

- investment opinion
- one-line conclusion
- exactly three executive summary bullets
- macro analysis
- fundamental/accounting analysis
- news/momentum analysis
- YouTube/guru analysis
- final judgement
- chart JSON block

It also writes `state["chart_data"]`, `state["final_report"]`, and sets status to `report_generated`.

### render_markdown_report Dependencies

The renderer depends on the current output shape and field names. It also depends on Python-calculated prices and final opinion. The analysis model must not invent or rename:

- `investment_opinion`
- `one_line_conclusion`
- `executive_summary`
- `macro_analysis`
- `fundamental_analysis`
- `momentum_analysis`
- `guru_analysis`
- `final_conclusion`
- `chart_data`

### OpenAI Structured-Output Replacement Proposal

Replace CrewAI with a direct OpenAI structured-output call:

1. Define a schema equivalent to `AnalysisOutput`.
2. Pass compacted inputs from `compact_analysis_inputs()`.
3. Force `investment_opinion` to the system-derived value.
4. Keep price guidance from Python calculations.
5. Validate that `executive_summary` has exactly three items.
6. Validate `chart_data` length/order against accounting arrays.
7. Pass the structured output into the unchanged `render_markdown_report()`.

### Risks

- Markdown parser breakage if output fields or headings change.
- Chart display breakage if `chart_data` changes.
- Opinion mismatch between system score and generated prose.
- Summary extraction breakage if report sections change.
- Higher blast radius than earlier steps because this step feeds final markdown directly.

## 8. Markdown/API Compatibility Requirements

The following must remain unchanged during CrewAI removal:

- Existing API response fields.
- Existing report markdown headings.
- Existing `chart_data` JSON handling.
- Existing price labels:
  - `현재가`
  - `권장 매수가`
  - `하락 시 방어선/저항선`
- Domestic stock price unit: `원`.
- US stock price unit: `$`.
- Frontend KRW conversion is rendering-only and should not force markdown changes.
- Summary file format and `MACRO_DATA` comment block.
- `/api/report-status/{job_id}` optional `targets_status` behavior.

## 9. Recommended CrewAI Removal Order

1. **Macro direct function**
   - Batch-level, clearer output contract, and less tied to per-stock rendering.
   - Easy to validate with static/stub macro JSON.

2. **Accounting direct function**
   - Mostly data fetch and Python validation already owns PASS/FAIL scoring.
   - More risk than macro because it feeds price targets and chart data.

3. **Research direct function**
   - Search result filtering can be made deterministic first.
   - Optional structured output can be introduced after raw search validation.

4. **Youtube RAG direct function**
   - Depends on local vector search and pending live-video safeguards.
   - Should wait until search interfaces are stable.

5. **Analysis OpenAI structured output**
   - Highest markdown compatibility risk.
   - Should be last among analysis steps because it directly feeds final report rendering.

6. **Remove CrewAI runtime imports**
   - Only after all steps no longer instantiate `Crew`, `Agent`, or `Task`.

7. **Remove `crewai` / `crewai-tools` from requirements**
   - Only after runtime imports are gone and tests pass.

8. **Migrate Chroma to `langchain_chroma`**
   - Do this last to avoid Chroma/CrewAI compatibility conflicts.

## 10. Step-by-Step Risks

### Macro

- Output shape mismatch for `MACRO_DATA`.
- Macro accidentally running per stock.
- Neutral fallback behavior changing.

### Accounting

- Missing fields used by price calculation.
- PASS/FAIL criteria drifting.
- One-stock failure stopping the whole batch.
- Chart source arrays changing order.

### Research

- External API calls during tests.
- Invalid news treated as valid.
- Sentiment thresholds changing final opinion.

### Youtube RAG

- Chroma/CrewAI dependency conflict.
- Accidentally triggering update/download/Whisper jobs.
- `content_type` or freshness logic changing guru weight.
- Pending live video safeguards being bypassed.

### Analysis

- Markdown headings or price labels changing.
- `chart_data` JSON no longer parseable by frontend.
- Summary save/extraction breakage.
- Final opinion mismatch.

### Cross-Cutting

- API response breakage.
- `status_callback` / `targets_status` not updating.
- Multi-stock failure isolation breakage.
- Summary save completion conditions changing.
- External API calls during automated validation.

## 11. Validation Plan

### Safe Static/Compile Commands

Use these when runtime code is changed in later steps:

```powershell
python -B -m py_compile main.py api.py graphs\report_graph.py pipelines\report_pipeline.py schemas\report_state.py
python -B -c "import api; print('api import ok')"
```

If frontend is affected:

```powershell
npm run build
```

### Mock/Stub Validation Suggestions

- Stub macro tool output and verify `macro_json`, `macro_score`, and `macro_score_reasons`.
- Stub accounting tool output and verify PASS/FAIL isolation.
- Stub research search results and verify neutral fallback for no valid news.
- Stub YouTube local search results and verify `guru_weight`.
- Stub final structured output and verify unchanged markdown headings and chart JSON.
- Stub `status_callback` and verify node-level `current_step` updates.

### Manual Real-App Tests for User

The user should manually run:

- One-stock report generation.
- Two-stock report generation.
- One passing stock plus one failing stock.
- Summary update check.
- Detailed report chart display check.
- Main page report card display check.
- `/api/report-status/{job_id}` progress UI check.

### Commands Codex Must Not Run During Migration Validation Without Explicit Approval

- `/api/run-report`
- Real report generation from frontend or backend
- YouTube update
- Whisper/audio download
- ChromaDB rebuild
- Embedding jobs
- `pip install`, `pip uninstall`, `pip upgrade`
- Chroma migration to `langchain_chroma` before CrewAI and `crewai-tools` are removed

## 12. Recommended Next Task

The first CrewAI step to replace should be **Macro**.

Macro is the safest first removal because it is batch-level, has a clear `MacroOutput` contract, already relies on Python for scoring, and is less tied to per-stock report markdown than Analysis. Replacing Macro first also validates the direct-function pattern without risking chart rendering, summary extraction, or per-stock failure isolation.
