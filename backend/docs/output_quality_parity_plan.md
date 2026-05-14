# Output Quality Parity Plan

## 1. Current Direct Runtime Architecture

The active runtime is CrewAI-free. FastAPI calls `pipelines/report_pipeline.py`, which delegates to `main.run_financial_crew()`. The report flow is orchestrated by LangGraph in `graphs/report_graph.py` with `ReportState` as the shared state object.

Current node order:

```text
validate_input
-> macro
-> accounting
-> research
-> youtube_rag
-> price
-> analysis
-> save_summary
-> finalize
```

Current implementation split:

- Macro: direct `collect_macro_data()` call in `flows/macro/tool.py`, then Python scoring in `main.calculate_macro_score()`.
- Accounting: direct `collect_financial_data()` call in `flows/accounting/tool.py`, then Python validation and scoring in `main.run_accounting_step()`.
- Research: direct Serper news search through `flows/research/tool.py`, then Python dedupe, scoring, and summary assembly in `main.py`.
- Youtube RAG: direct local Chroma search through `flows/youtube/tool.py`, then Python content type, freshness, and score handling in `main.py`.
- Analysis: direct OpenAI structured-output call in `main.call_analysis_structured_output()`, normalized by `main.normalize_analysis_output()`, rendered by `main.render_markdown_report()`.

Legacy `agent.py` and `task.py` files remain as reference material only. They are not part of active runtime imports.

## 2. Old CrewAI Prompt Responsibilities By Step

The old CrewAI prompts carried more than schema definitions. They encoded analyst behavior, hallucination control, source policy, scoring boundaries, recency rules, and wording constraints.

Important note: several legacy prompt files now contain mojibake, so exact Korean wording cannot be fully trusted from the current source alone. The responsibility analysis below is based on readable identifiers, schemas, surviving English tokens, direct runtime code, and repeated rule structure visible in the legacy files.

## 3. New Direct Implementation Behavior By Step

The new direct implementation is technically simpler and more deterministic, but it no longer has the same amount of natural-language analyst instruction at every step.

The biggest behavioral shift is:

- Old CrewAI steps asked LLM agents to transform tool output into rich structured interpretation while following many guardrails.
- New direct steps mostly preserve raw data and compute simple scores with Python rules.
- The final Analysis structured-output call now carries most of the writing burden, but its prompt is much shorter than the old AnalysisTask prompt.

## 4. Missing Instructions Or Quality Gaps

Likely lost or weakened instructions:

- Do not invent missing facts, titles, links, dates, prices, targets, or claims.
- Use only tool-returned fields as evidence.
- Keep news financial numbers out of final financial claims when they conflict with accounting data.
- Treat YouTube as investment philosophy and risk-management context, not a price-target source.
- Distinguish stock-specific YouTube mentions from general market, mindset, risk, or psychology content.
- Apply recency rules explicitly to news and YouTube.
- Convert large financial values into human-readable Korean or US units in prose.
- Keep section lengths controlled and avoid vague filler.
- Preserve the system-calculated investment opinion, price guide, and defensive line.
- Explain risk separately instead of turning every Buy into an overly optimistic report.

## 5. Fields Carrying Interpretation Vs Raw Data

Raw or mostly raw data fields:

- `macro_json`: macro indicators, 1-month changes, warnings, validity.
- `acc_data`: yfinance-derived values, moving averages, revenue, net_income, fcf, valuation metrics.
- `research_json.results`: normalized news titles, sources, dates, links, snippets.
- `youtube_json.selected_docs` or derived details: local Chroma search results and metadata.
- `chart_data`: raw numeric chart fields for frontend compatibility.

Interpretation fields:

- `macro_score`, `macro_score_reasons`: Python interpretation of macro risk.
- `fundamental_score`, `fundamental_score_reasons`: Python interpretation of financial quality.
- `sentiment`: Python mapping from research score to positive, neutral, or negative.
- `guru_score`, `guru_weight`: Python mapping from YouTube content type and freshness.
- `investment_opinion`: system-calculated final opinion.
- `one_line_conclusion`, `executive_summary`, `macro_analysis`, `fundamental_analysis`, `momentum_analysis`, `guru_analysis`, `final_conclusion`: generated narrative from direct OpenAI structured output.

Quality parity depends mostly on improving interpretation prompts and deterministic helper summaries without changing public API or markdown format.

## 6. Analysis Prompt Parity Gap

Old Analysis responsibilities:

- Preserve system-calculated `investment_opinion`.
- Do not freely override price guide values.
- Use accounting data as the only source for financial numbers.
- Do not use news or YouTube to invent revenue, profit, EPS, target prices, or valuation numbers.
- Convert large financial values into readable Korean stock or US stock units.
- Keep chart data in T-2, T-1, T order using raw accounting arrays.
- Interpret YouTube differently by `content_type`.
- For non-specific YouTube content, translate it into general investment attitude or risk-control guidance instead of direct buy/sell recommendation.
- Use exactly three executive summary bullets.
- Avoid markdown inside structured-output fields.
- Avoid unsupported claims.

Current direct Analysis behavior:

- Preserves `investment_opinion` by normalization.
- Uses a short system prompt: structured data only, do not override opinion, do not invent prices, earnings, or YouTube claims.
- Passes compacted accounting, macro, research, and YouTube JSON.
- Requests concise Korean fields and chart data mapping.

Parity gap:

- The current prompt is too short to reproduce the old report style.
- It does not fully encode YouTube content-type interpretation rules.
- It does not strongly instruct unit conversion in prose.
- It does not strongly separate risk commentary from investment opinion.
- It does not define expected section depth, tone, evidence style, or source limitations as carefully as the old task.

## 7. Macro Parity Gap

Old Macro responsibilities:

- Use the macro data tool output exactly.
- Do not invent or adjust numeric values.
- Preserve null values.
- Do not calculate market score in the LLM step; Python rules handle scoring.
- Map tool JSON into a schema containing exchange rate, US 10-year yield, Nasdaq, WTI, VIX, monthly changes, warnings, briefing, validity, and error.

Current direct Macro behavior:

- Calls `collect_macro_data()` directly.
- Calculates `macro_score` in Python.
- Runs once per batch and injects macro context into each stock state.

Parity gap:

- The direct tool has some static Korean strings that should be reviewed for readability before prompt restoration.
- The macro briefing is mechanically assembled and may be less analyst-like than the old agent output.
- Risk warning wording may be less explanatory.

## 8. Accounting Parity Gap

Old Accounting responsibilities:

- Use financial data tool output exactly.
- Preserve array order from past to recent.
- Do not invent or adjust numeric values.
- Do not decide PASS or FAIL in the LLM; Python rules handle validation.
- Return schema fields such as current price, PER, PBR, dividend yield, moving averages, ROE, revenue, net income, FCF, debt ratio, margin, sector, industry, summary, validity, and error.

Current direct Accounting behavior:

- Calls yfinance directly through `collect_financial_data()`.
- Configures a writable yfinance cache directory.
- Applies Python validation for insufficient data, negative income, negative FCF, zero revenue, and high debt ratio.
- Calculates `fundamental_score` and price guide separately.

Parity gap:

- The current data summary is short and may contain less explanatory context.
- Some Python score reason wording should be audited for correctness and clarity.
- The old report-writing prompt included stronger guidance for unit conversion and avoiding raw noisy floats in prose.

## 9. Research Parity Gap

Old Research responsibilities:

- Run multiple query types: recent news, price/supply/investor psychology, earnings or broker reports, industry and competitors, English global news.
- Use fallback queries if results are weak.
- Validate that title or snippet is relevant to the company.
- Use only real search result title, source, date, link, and snippet.
- Avoid unsupported article titles, URLs, broker names, target prices, and dates.
- Exclude vague blogs, ads, low-quality articles, and duplicate content.
- Avoid using financial numbers from news as accounting facts.
- Score sentiment in defined ranges and set momentum strength.
- Keep summary length controlled.

Current direct Research behavior:

- Builds a similar query list.
- Calls Serper directly.
- Normalizes and deduplicates results.
- Uses keyword hits to score sentiment.
- Produces a compact summary from top results.

Parity gap:

- Relevance filtering is weaker than the old instruction set.
- Quality filtering for weak sources, ads, and blogs is limited.
- Sentiment scoring is keyword-based and may miss context.
- The old prompt had explicit instructions to avoid unsupported broker details and target prices; direct code should preserve that in future summary formatting.

## 10. Youtube RAG Parity Gap

Old Youtube responsibilities:

- Search local YouTube transcripts.
- Separate stock-specific content from market, mindset, risk, psychology, and no-data content.
- Use selected transcript docs only.
- Do not invent prices, target prices, earnings numbers, or direct guru statements.
- Treat non-specific content as investment philosophy or risk-control guidance, not direct stock recommendation.
- Apply freshness levels and date rules.
- Keep guru score neutral for non-specific content.
- Provide key strategy, mindset summary, market principle, risk control, details, validity.

Current direct Youtube behavior:

- Uses `langchain_chroma.Chroma` through local search.
- Performs Plan A company-specific search and Plan B market or mindset fallback search.
- Computes freshness and content type hints.
- Builds a compact direct result with score and details.

Parity gap:

- Many interpretation guide strings in `flows/youtube/tool.py` appear mojibake-corrupted and should be cleaned before relying on them as prompt context.
- The direct builder collapses several fields into the same `details` text, reducing nuance.
- Old prompt had more careful content-type-specific writing rules than the current direct summary.
- Current keyword scoring is simpler than old LLM interpretation.

## 11. Safe Restoration Order

Recommended order:

1. Korean/mojibake cleanup in active direct tool strings and status/error strings.
2. Analysis structured-output prompt parity restoration.
3. Youtube RAG interpretation guide cleanup and direct summary improvement.
4. Research relevance and source-quality filtering.
5. Accounting summary and score reason wording cleanup.
6. Macro briefing wording cleanup.
7. Optional golden-file report comparison against old known-good reports.

Why Analysis first after encoding cleanup:

- Report quality difference is most visible in final prose.
- It can absorb more detailed instructions without changing API fields.
- It should preserve `investment_opinion`, chart shape, markdown headings, and price labels.
- It is easier to mock than full data collection.

Why not start with Macro or Accounting:

- They mostly produce data and scores.
- They affect correctness, but less of the visible report tone.
- Their quality gaps are important but narrower than the final report-writing gap.

## 12. Risks

Main risks while restoring parity:

- Output shape mismatch with `DirectAnalysisOutput`.
- Markdown parser breakage if headings or chart data format changes.
- Frontend chart breakage if `chart_data` fields or order change.
- Summary save breakage if report extraction assumptions change.
- `investment_opinion` drift if the LLM is allowed to override system scoring.
- Direct YouTube content being interpreted as a stock-specific recommendation when it is only market or mindset guidance.
- News snippets being treated as financial facts.
- Reintroducing too much prompt length and causing structured-output parsing failures.
- Accidentally reintroducing CrewAI imports.
- Running external APIs during tests unintentionally.
- Korean mojibake returning through copied legacy prompt text.

## 13. Validation Plan

Static validation:

```powershell
cd backend
python -B -m py_compile main.py api.py graphs\report_graph.py pipelines\report_pipeline.py schemas\report_state.py services\summary_service.py services\report_file_service.py services\report_metadata_service.py flows\macro\tool.py flows\accounting\tool.py flows\research\tool.py flows\youtube\tool.py vector_db\build_vector_db.py
python -B -c "import api; print('api import ok')"
python -B -c "import main; print('main import ok')"
python -B -c "from langchain_chroma import Chroma; print('langchain_chroma import ok')"
```

Mock validation:

- Mock `call_analysis_structured_output()` and confirm `normalize_analysis_output()` preserves system `investment_opinion`.
- Mock Analysis output and confirm markdown headings remain unchanged.
- Mock `chart_data` and confirm fields remain `period`, `revenue`, `net_profit`, `fcf`.
- Mock Research results with duplicate or irrelevant articles and confirm filtering behavior.
- Mock YouTube search results for `SPECIFIC`, `MARKET`, `MINDSET`, `RISK`, `PSYCHOLOGY`, and `N/A`.

Manual user-run app validation:

- 1-stock report generation.
- 2-stock report generation with one Korean and one US stock.
- Confirm `summary_saved=true`.
- Confirm macro runs once per batch.
- Confirm report cards, detail page, chart rendering, and summary extraction still work.
- Compare generated report quality with older known-good reports.

Commands Codex should not run during documentation or prompt-only work:

- `/api/run-report`
- real report generation
- real OpenAI calls
- YouTube update
- pending live processing
- Whisper or audio download
- Chroma rebuild
- embedding jobs
- pip install, uninstall, or upgrade

## 14. Korean Encoding And Mojibake Safety Plan

Before restoring any prompt text:

- Do not copy mojibake text from legacy files directly into active prompts.
- Reconstruct Korean instructions manually in clean UTF-8.
- Keep source files encoded as UTF-8.
- After each prompt or text change, scan edited files for mojibake patterns.
- Prefer small patches and review diff output before validation.

Recommended scan approach:

- Search for common CP949/UTF-8 mojibake fragments before finishing any Korean prompt or fallback-message change.
- Keep the exact pattern list in the task checklist or reviewer notes, not inside runtime-facing documentation, so the document itself stays clean when scanned.

Files that need special caution:

- `flows/macro/tool.py`
- `flows/accounting/tool.py`
- `flows/youtube/tool.py`
- `graphs/report_graph.py`
- `pipelines/report_pipeline.py`
- legacy `agent.py` and `task.py` files if they are used as reference

## Recommended First Restoration Step

The first restoration step should be Analysis prompt parity, but only after active Korean/mojibake strings used as direct tool context are cleaned.

Practical first implementation task:

1. Keep runtime CrewAI-free.
2. Expand the direct Analysis structured-output prompt with the old safety rules in clean UTF-8.
3. Preserve the same `DirectAnalysisOutput` schema.
4. Preserve system `investment_opinion`.
5. Preserve markdown headings, price labels, and chart data.
6. Validate with mocked structured output before any real report generation.
