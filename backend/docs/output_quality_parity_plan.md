# Output Quality Parity Plan

## 1. Current Direct Runtime Architecture

The active runtime is CrewAI-free. FastAPI receives report requests, `pipelines/report_pipeline.py` calls `main.run_financial_crew()`, and LangGraph in `graphs/report_graph.py` orchestrates the stock report flow with `ReportState`.

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

Current active execution model:

- Macro uses direct `collect_macro_data()` plus Python `macro_score` rules.
- Accounting uses direct `collect_financial_data()` plus Python validation, scoring, and failed-report fallback.
- Research uses direct Serper/news search, Python normalization, dedupe, and sentiment scoring.
- Youtube RAG uses direct local YouTube search over `langchain_chroma.Chroma` read path.
- Analysis uses direct OpenAI structured output, then deterministic Python markdown rendering.

Legacy `backend/flows/*/agent.py` and `backend/flows/*/task.py` files remain reference material only. They must not be imported or executed to restore quality.

## 2. Old CrewAI Prompt Responsibilities By Step

The old Agent/Task prompts did more than call tools. They encoded rules about evidence, interpretation boundaries, source quality, no-hallucination behavior, and report-writing tone.

Important caution:

- Several legacy prompt files are mojibake-corrupted, so old text should not be copied directly.
- Only stable responsibilities should be extracted.
- CrewAI execution should not return.
- Facts, final scores, prices, and final investment opinion must stay system-controlled.

## 3. New Direct Implementation Behavior By Step

The direct implementation is more deterministic and easier to validate, but some analyst instructions became thinner:

- Direct tools return raw or lightly interpreted data.
- Python rules calculate scores and final opinion.
- The final Analysis structured-output prompt carries most narrative responsibility.
- Markdown headings, price table, and chart data are deterministic Python output.

This is the right runtime shape. The quality restoration work should add safe constraints around it, not bring back Agent/Task execution.

## 4. Missing Instructions Or Quality Gaps

Likely lost during migration:

- Senior analyst tone and section depth.
- Section-specific reasoning instead of generic summary prose.
- Explicit explanation of how system score and guru insight combine.
- Stronger distinction between system-calculated opinion and YouTube/guru context.
- News synthesis rather than raw news listing.
- YouTube content-type handling for direct stock mention versus general principle.
- Explicit missing-data language.
- Stronger ban on invented numbers, dates, news, target prices, or YouTube comments.
- Better risk discussion inside final judgement.

Do not restore these by letting the LLM decide facts. Restore them through deterministic preprocessing where possible and prompt constraints only where prose synthesis is required.

## 5. Fields Carrying Interpretation Vs Raw Data

Raw or mostly raw fields:

- `macro_json`: exchange rate, US 10Y yield, Nasdaq, WTI, VIX, changes, warnings, validity.
- `acc_data`: yfinance-derived price, valuation, moving averages, revenue, net income, FCF, debt, margin, sector, industry.
- `research_json.results`: titles, sources, dates, links, snippets.
- `youtube_json.selected_docs` or derived details: local Chroma search documents and metadata.
- `current_price`, `target_buy_price`, `defense_price`: deterministic price guide values.
- `chart_data`: frontend-compatible raw numeric data.

System-controlled interpretation:

- `macro_score`
- `macro_score_reasons`
- `fundamental_score`
- `fundamental_score_reasons`
- `sentiment`
- `guru_score`
- `guru_weight`
- `investment_opinion`

LLM-written interpretation:

- `one_line_conclusion`
- `executive_summary`
- `macro_analysis`
- `fundamental_analysis`
- `momentum_analysis`
- `guru_analysis`
- `final_conclusion`

The LLM may explain supplied data, but it must not create new facts or override system-controlled values.

## 6. Analysis Prompt Parity Gap

Old Analysis Agent/Task did:

- Wrote like a senior investment analyst, not a generic summarizer.
- Preserved system-calculated `investment_opinion`.
- Used supplied price guide without changing it.
- Used accounting data as the only financial-number source.
- Treated news as business momentum, not audited financial truth.
- Treated YouTube as guru insight, strategy, psychology, and risk context.
- Distinguished stock-specific YouTube mentions from general market or mindset principles.
- Required exactly three executive summary bullets.
- Kept `one_line_conclusion` concise.
- Avoided markdown inside schema fields.
- Avoided unsupported claims and invented data.

Current direct Analysis does:

- Calls OpenAI structured output directly.
- Normalizes `investment_opinion` back to the system value after the call.
- Passes compacted macro, accounting, research, and YouTube JSON.
- Renders markdown with deterministic Python.

What may have been lost:

- Report tone and depth.
- Rich section-specific reasoning.
- Explicit final judgement logic.
- Separate downside-risk discussion.
- Strong YouTube content-type interpretation.
- Clear instruction to avoid vague filler.

Restore as deterministic rules:

- Force `investment_opinion` to the system value.
- Keep `chart_data` derived from accounting arrays.
- Keep markdown headings and price table in Python.
- Keep price units in Python.
- Keep final opinion calculation in Python.

Restore as prompt/writing constraints:

- Senior analyst tone.
- Section-specific reasoning.
- Exactly three executive summary items.
- Concise one-line conclusion.
- Explain how macro, accounting, news, YouTube, price guide, and risks support the system opinion.
- State missing data cautiously.
- Do not repeat the same sentence across sections.

Must remain system-controlled:

- `investment_opinion`
- current price
- target buy price
- defense price
- financial numbers
- chart data
- final markdown headings

Do not copy blindly:

- Any mojibake-corrupted Korean prompt text.
- Any old instruction that lets LLM compute prices, scores, or final opinion.
- Any old Agent/Task execution pattern.

## 7. Macro Parity Gap

Old Macro Agent/Task did:

- Used the macro data tool output.
- Mapped tool JSON into macro schema.
- Preserved null values.
- Avoided inventing or adjusting macro indicator values.
- Left score calculation to Python rules.
- Produced macro briefing and validity fields.

Current direct Macro does:

- Calls `collect_macro_data()` directly.
- Calculates `macro_score` and `macro_score_reasons` in Python.
- Runs once per batch and injects macro context into each stock state.

What may have been lost:

- More readable macro briefing.
- Clear pressure/support explanation for FX, US 10Y yield, Nasdaq, WTI, and VIX.
- Better missing-data language.

Restore as deterministic rules:

- Keep macro batch-once behavior.
- Keep score thresholds in Python.
- Keep `macro_score_reasons` in Python.
- Keep missing-data fallback deterministic.

Restore as prompt/writing constraints:

- In Analysis, explain whether each macro factor is pressure, support, or neutral.
- Avoid pretending missing macro values are known.

Must remain system-controlled:

- Macro values.
- Macro score.
- Macro score reasons.
- Macro validity.

Do not copy blindly:

- Mojibake macro labels.
- Any LLM instruction that asks the model to calculate macro scores.

## 8. Accounting Parity Gap

Old Accounting Agent/Task did:

- Used the financial data tool output exactly.
- Preserved revenue, net income, and FCF array order from past to recent.
- Avoided inventing or correcting numeric values.
- Left PASS/FAIL and investment eligibility checks to Python rules.
- Returned current price, PER, PBR, dividend yield, moving averages, ROE, revenue, net income, FCF, debt ratio, margin, sector, industry, summary, validity, and error.

Current direct Accounting does:

- Calls `collect_financial_data()` directly.
- Configures a writable yfinance cache directory.
- Validates data sufficiency.
- Builds failed report items for invalid or failing financial cases.
- Calculates `fundamental_score` and `fundamental_score_reasons`.
- Leaves price target calculation to `run_price_step()`.

What may have been lost:

- Richer revenue trend interpretation.
- Richer net income and FCF quality explanation.
- Clearer explanation of data shortage versus financial weakness.
- Cleaner human-readable unit guidance inside final prose.

Restore as deterministic rules:

- Keep failed-report fallback deterministic.
- Keep financial validation in Python.
- Keep `fundamental_score_reasons` in Python.
- Keep chart data from raw arrays.
- Keep price guide calculation in Python.

Restore as prompt/writing constraints:

- Explain revenue trend, profit trend, FCF quality, debt, margin, valuation, and moving-average context using only `acc_data`.
- Do not use news snippets as audited financial numbers.
- Use cautious wording when accounting fields are missing.

Must remain system-controlled:

- `acc_data`
- `fundamental_score`
- `fundamental_score_reasons`
- `failed_report_item`
- `current_price`
- `target_buy_price`
- `defense_price`
- `chart_data`

Do not copy blindly:

- Any old instruction that allows LLM to decide PASS/FAIL.
- Any old instruction that allows LLM to modify financial numbers.

## 9. Research Parity Gap

Old Research Agent/Task did:

- Ran multiple query categories: recent news, price/supply/investor psychology, earnings or broker reports, industry and competitors, and English global news.
- Used fallback queries when results were weak.
- Validated relevance against company name.
- Used only real title, source, date, link, and snippet fields.
- Excluded weak, duplicate, or unsupported results.
- Avoided invented broker names, target prices, URLs, and dates.
- Avoided treating news financial numbers as accounting facts.
- Produced sentiment score, momentum strength, summary, and validity.

Current direct Research does:

- Builds similar query categories.
- Calls Serper/news directly.
- Normalizes and deduplicates results.
- Scores sentiment with keyword rules.
- Produces a compact news summary and result list.

What may have been lost:

- Strong source-quality filtering.
- Better relevance checks.
- Nuanced positive, negative, and neutral issue classification.
- Better synthesis of news into business momentum.

Restore as deterministic rules:

- Improve relevance and duplicate filtering.
- Classify positive, negative, and neutral issue hits using explicit keyword/rule lists.
- Keep no-result fallback deterministic.
- Keep sentiment mapping deterministic.

Restore as prompt/writing constraints:

- In Analysis, synthesize business momentum instead of listing raw news.
- Mention source/date only when provided.
- Do not invent or infer broker details beyond supplied data.
- Treat news as market signal, not audited accounting evidence.

Must remain system-controlled:

- Serper result fields.
- `sentiment_score`
- `sentiment`
- no-result fallback.

Do not copy blindly:

- Any old prompt text that implies the LLM can fabricate missing article details.
- Any old scoring behavior not backed by deterministic input.

## 10. Youtube RAG Parity Gap

Old Youtube Agent/Task did:

- Searched local YouTube transcript data.
- Distinguished `SPECIFIC`, `MARKET`, `MINDSET`, `RISK`, `PSYCHOLOGY`, and no-data cases.
- Used selected transcript docs only.
- Treated non-specific content as general principle, not direct stock recommendation.
- Applied date and freshness rules.
- Kept guru score neutral for non-specific content.
- Produced strategy, mindset, market principle, risk control, insight details, and validity.

Current direct Youtube RAG does:

- Uses local Chroma retrieval through `langchain_chroma.Chroma`.
- Runs Plan A stock-specific search.
- Runs Plan B market, mindset, and risk fallback search.
- Calculates freshness, content type hint, guru score, and guru weight.
- Builds a direct result for Analysis.

What may have been lost:

- Nuanced content-type-specific prose.
- Separate strategy, psychology, risk, and market-principle summaries.
- Strong guardrails against turning general principles into direct recommendations.
- Richer no-result fallback language.

Restore as deterministic rules:

- Keep content type and freshness classification deterministic.
- Keep guru score neutral unless content is recent and stock-specific.
- Keep selected docs as the only evidence source.
- Keep no-result fallback deterministic.

Restore as prompt/writing constraints:

- In Analysis, explain whether insight is direct-stock or general-principle.
- For `MARKET`, discuss market posture.
- For `MINDSET`, discuss investor behavior and patience.
- For `RISK`, discuss position sizing, split buying, and defense.
- For `PSYCHOLOGY`, discuss sentiment and price confirmation.
- Do not invent guru comments.

Must remain system-controlled:

- `content_type`
- `freshness_level`
- `guru_score`
- `guru_weight`
- selected docs and dates.

Do not copy blindly:

- Mojibake YouTube prompt text.
- Any instruction that treats general market commentary as a direct recommendation.
- Any old wording that implies YouTube can produce target prices.

## 11. Hallucination Defense Plan

Core principle:

- The LLM explains provided data. It does not create new data.

Defense layers:

1. Deterministic Python owns data collection, validation, scoring, price guide, final opinion, chart data, markdown headings, and summary save.
2. Structured-output schema restricts the LLM to known report fields.
3. Prompt constraints forbid invented numbers, prices, dates, articles, links, YouTube comments, broker names, and target prices.
4. Analysis input should clearly label raw data, derived scores, and missing values.
5. Missing values must be described as unavailable or limited.
6. News numbers must not become accounting facts.
7. YouTube must not become a price-target source.
8. System-calculated `investment_opinion` is restored after model output and must be treated as final.

Future validation should use mock inputs that intentionally omit data and confirm the output uses cautious language rather than fabricated detail.

## 12. Safe Restoration Order

Recommended order:

1. Analysis structured-output prompt parity.
2. Youtube RAG interpretation guide cleanup and content-type summary improvement.
3. Research relevance, source-quality, and sentiment reasoning improvement.
4. Accounting summary wording and trend interpretation improvement.
5. Macro briefing wording and pressure/support explanation improvement.
6. Optional golden-file comparison against old known-good reports.

Why Analysis first:

- It has the largest visible effect on report quality.
- It can restore tone and synthesis without changing API fields.
- It can be validated with mocked structured output.
- It does not require reintroducing CrewAI.

## 13. Risks

Risks while restoring parity:

- Output schema mismatch.
- Markdown parser breakage.
- Chart rendering breakage.
- Summary extraction breakage.
- LLM overriding final opinion.
- News snippets being treated as audited financial facts.
- General YouTube principles being interpreted as direct stock calls.
- Prompt length causing structured-output parse failures.
- Accidentally copying mojibake from legacy prompts.
- Accidentally reintroducing CrewAI imports.
- Accidentally running real external APIs during validation.

Mitigation:

- Keep patches small.
- Use mock validation before real generation.
- Preserve deterministic Python rendering.
- Scan edited files for mojibake.
- Search active runtime for CrewAI imports after changes.

## 14. Validation Plan

This document step requires no runtime validation. For future implementation steps:

Static validation:

```powershell
cd backend
python -B -m py_compile main.py api.py graphs\report_graph.py pipelines\report_pipeline.py schemas\report_state.py services\summary_service.py services\report_file_service.py services\report_metadata_service.py flows\macro\tool.py flows\accounting\tool.py flows\research\tool.py flows\youtube\tool.py vector_db\build_vector_db.py
python -B -c "import api; print('api import ok')"
python -B -c "import main; print('main import ok')"
python -B -c "from langchain_chroma import Chroma; print('langchain_chroma import ok')"
```

Mock validation:

- Mock Analysis structured output and confirm markdown headings are unchanged.
- Confirm `investment_opinion` remains the system value.
- Confirm `chart_data` fields remain `period`, `revenue`, `net_profit`, `fcf`.
- Mock missing macro, news, and YouTube fields and confirm cautious language.
- Mock `SPECIFIC`, `MARKET`, `MINDSET`, `RISK`, `PSYCHOLOGY`, and no-result YouTube cases.

Manual user-run validation:

- 1-stock report generation.
- 2-stock report generation with one Korean and one US stock.
- Confirm `summary_saved=true`.
- Confirm macro runs once per batch.
- Compare generated prose quality against older known-good reports.

Commands to avoid during documentation and prompt-only steps:

- `/api/run-report`
- real report generation
- real OpenAI calls
- YouTube update
- pending live processing
- Whisper or audio download
- Chroma rebuild
- embedding jobs
- pip install, uninstall, or upgrade

## 15. Korean Encoding And Mojibake Safety Plan

Rules:

- Keep markdown and Python files as UTF-8.
- Do not copy mojibake text from legacy Agent/Task files.
- Reconstruct Korean instructions manually in readable Korean.
- Scan newly created or edited text before finishing.
- If a scan pattern appears only because the document lists scan patterns, remove or reword that list so scans remain meaningful.

Files requiring extra caution:

- `backend/flows/macro/tool.py`
- `backend/flows/accounting/tool.py`
- `backend/flows/youtube/tool.py`
- `backend/graphs/report_graph.py`
- `backend/pipelines/report_pipeline.py`
- legacy `backend/flows/*/agent.py`
- legacy `backend/flows/*/task.py`

For this documentation file, no mojibake text should remain.

## Recommended First Restoration Step

The first restoration step should be Analysis prompt parity.

Implementation target:

- Keep runtime CrewAI-free.
- Expand `call_analysis_structured_output()` with clean UTF-8 safety and writing constraints.
- Preserve the existing structured-output schema.
- Preserve deterministic markdown rendering.
- Preserve final `investment_opinion`.
- Validate with mocked structured output before any real report generation.
