import os
from typing import List

from pydantic import BaseModel, Field

from services.runtime_config_service import get_openai_analysis_model


class DirectChartData(BaseModel):
    period: str = Field(description="T-2, T-1, T")
    revenue: float = Field(description="revenue")
    net_profit: float = Field(description="net profit")
    fcf: float = Field(description="free cash flow")


class DirectAnalysisOutput(BaseModel):
    investment_opinion: str
    one_line_conclusion: str
    executive_summary: List[str]
    macro_analysis: str
    fundamental_analysis: str
    momentum_analysis: str
    guru_analysis: str
    final_conclusion: str
    chart_data: List[DirectChartData]


def build_analysis_messages(
    company: str = "",
    analysis_inputs=None,
    final_opinion: str = "Hold",
    target_buy_price=None,
    defense_price=None,
):
    target_buy_price_text = (
        f"{target_buy_price:,.2f}"
        if isinstance(target_buy_price, (int, float))
        else "N/A"
    )
    defense_price_text = (
        f"{defense_price:,.2f}"
        if isinstance(defense_price, (int, float))
        else "N/A"
    )

    system_prompt = (
        "You are a senior investment analyst writing a disciplined Korean stock "
        "report for real investors. Return only structured data matching the schema. "
        "Do not write markdown in field values. The provided system investment "
        "opinion is final and must not be changed. Never invent revenue, profit, "
        "FCF, prices, dates, news, YouTube comments, target prices, or analyst "
        "claims. Use only the supplied macro, accounting, research, YouTube, "
        "price-guide, and system-score inputs. If a value is missing, say it is "
        "unavailable and interpret cautiously. Facts, numbers, prices, scores, "
        "chart data, and final investment opinion are system-controlled; your role "
        "is to synthesize and explain them."
    )

    user_prompt = (
        f"Company: {company}\n"
        f"System investment opinion: {final_opinion}\n"
        f"권장 매수가: {target_buy_price_text}\n"
        f"방어선: {defense_price_text}\n\n"
        f"Accounting data:\n{analysis_inputs['accounting']}\n\n"
        f"Macro data:\n{analysis_inputs['macro']}\n\n"
        f"Research data:\n{analysis_inputs['research']}\n\n"
        f"YouTube data:\n{analysis_inputs['youtube']}\n\n"
        "Write the report as a senior investment analyst, not as a generic summary. "
        "Explain why the final opinion follows from the system score, accounting "
        "quality, macro pressure/support, news sentiment, and guru insight. "
        "Distinguish the system-calculated opinion from YouTube/guru insight; "
        "YouTube is supporting context, not a source of target prices or direct "
        "buy/sell claims unless the provided content explicitly says so.\n\n"
        "Grounding rules:\n"
        "- Use only provided macro, accounting, research, YouTube, current price, "
        "권장 매수가, and 방어선 data.\n"
        "- Do not create missing facts, estimates, dates, article details, broker "
        "names, prices, revenue, profit, FCF, scores, or YouTube quotes.\n"
        "- If data is missing, stale, invalid, or weak, explicitly say the evidence "
        "is limited and keep the interpretation conservative.\n"
        "- News snippets may indicate momentum, but they are not audited financial "
        "statements. Do not use news numbers as accounting facts.\n"
        "- Deterministic Python code controls markdown headings, price table labels, "
        "price units, chart_data, and final investment opinion.\n"
        "- Do not mention KRW conversion for US stocks in markdown source; frontend "
        "rendering handles KRW conversion.\n\n"
        "Financial unit conversion safety:\n"
        "- chart_data values are raw KRW numbers for Korean stocks. revenue, "
        "net_profit, and fcf in chart_data are raw 원 values.\n"
        "- 1조원 = 1,000,000,000,000원. 1억원 = 100,000,000원.\n"
        "- If conversion is needed, use value_in_조원 = raw_value / "
        "1,000,000,000,000 and value_in_억원 = raw_value / 100,000,000.\n"
        "- Double-check magnitude before writing financial figures. For example, "
        "44,260,956,000,000원 -> 4.43조원 is wrong; it should be about "
        "44.26조원. 97,146,675,000,000원 -> 971조원 is wrong; it should "
        "be about 97.15조원.\n"
        "- Do not casually convert raw KRW values into 조원/억원 unless the "
        "conversion is certain. If unsure, do not restate exact converted "
        "figures. Prefer qualitative trend wording such as revenue increased, "
        "net profit improved, or FCF improved.\n"
        "- Prefer existing accounting/fundamental summary text if it already "
        "provides interpreted values. Do not invent financial figures not present "
        "in the input.\n\n"
        "Structured brief priority:\n"
        "- Macro data may contain macro_context. If macro_context exists, use it "
        "first for macro_analysis. Use market_regime, positive_factors, "
        "risk_factors, sector_impact, summary, and final_impact as explanation "
        "context only. Do not recalculate macro_score and do not invent macro "
        "indicators.\n"
        "- Research data may contain news_brief. If news_brief exists, use it first "
        "for momentum_analysis. Use sentiment, momentum_strength, "
        "key_positive_factors, key_risks, price_reflection, summary, final_impact, "
        "and evidence_items. Do not invent article facts, broker opinions, URLs, "
        "dates, target prices, or full article text. If price reflection is "
        "uncertain, keep wording cautious.\n"
        "- YouTube data may contain guru_strategy_context and guru_opinion. "
        "If guru_strategy_context exists, use it as common strategy context: "
        "recent_market_view, preferred_stock_style, avoid_stock_style, "
        "portfolio_principle, risk_control_rule, mindset_summary, action_guide, "
        "source_window, and evidence_items. If guru_opinion exists, use it as "
        "per-stock evidence: mention_type, sentiment, confidence, "
        "stock_relevance, opinion_impact, buy_upgrade_signal, "
        "price_discipline_note, risk_warning, summary, and evidence_items. "
        "Apply the common strategy to the current stock, but never treat "
        "guru_strategy_context alone as direct Buy evidence. Distinguish DIRECT "
        "stock opinion, SECTOR linkage, MARKET linkage, MINDSET-only guidance, "
        "and NONE/insufficient evidence. Do not treat MINDSET-only content as "
        "direct Buy evidence, do not invent YouTube quotes, and do not claim an "
        "exact latest-3 broadcast window unless source_window supports it.\n\n"
        "Korean wording rules:\n"
        "- Write the final report in natural Korean. Do not output Chinese or "
        "Japanese characters, mixed-language artifacts, or broken expressions "
        "unless they are part of a proper noun.\n"
        "- Avoid broken expressions such as '기대를示하며' or '추천 후견지명'. "
        "Use concise professional Korean instead.\n"
        "- Translate internal enum labels into natural Korean: BULLISH -> 긍정적, "
        "BEARISH -> 부정적, NEUTRAL -> 중립적, HIGH -> 높음, MEDIUM -> 중간, "
        "LOW -> 낮음, DIRECT -> 직접 언급, SECTOR -> 섹터 관련, MARKET -> "
        "시장 전반, MINDSET -> 투자 원칙/심리, NONE -> 직접 근거 없음.\n"
        "- Do not expose raw enum labels like 'bearish', 'low', 'DIRECT', or "
        "'MINDSET' in Korean report prose.\n"
        "- If guru evidence is weak or indirect, write '직접적인 매수 근거로 "
        "보기는 어렵습니다.' instead of awkward wording.\n"
        "- Keep sentences concise and professional.\n"
        "- Write all prose in natural Korean. Do not leave English price-guide or "
        "section labels inside Korean sentences. Use '권장 매수가', '방어선', "
        "'최종 결론', and '밸류에이션' instead.\n"
        "- Never output awkward shorthand or missing-space negation. Use polished wording "
        "such as '신규 매수는 보수적입니다' or '매수 매력은 제한적입니다'.\n"
        "- Avoid repeated sentence punctuation and keep Korean sentence spacing natural.\n"
        "- Do not mention specific calendar-year wording unless explicit year "
        "metadata is present in the provided data. Chart periods are T-2, T-1, T, "
        "so describe them as '최근 기간', 'T 기준', or '최근 연도 기준'.\n"
        "- Keep claims measured. Avoid hard claims beyond the system opinion.\n\n"
        "Field requirements:\n"
        "- investment_opinion: exactly the system investment opinion above. Do not "
        "override it. Ensure every section is consistent with this opinion while "
        "still discussing risks honestly.\n"
        "- one_line_conclusion: one concise Korean sentence, preferably within 40 "
        "Korean characters, with polished spacing and the strongest evidence-based "
        "reason. Avoid casual shorthand.\n"
        "- executive_summary: exactly 3 items. Each item must include a specific "
        "reason from macro, accounting, news, YouTube, price, or risk. Do not make "
        "all 3 bullets say the same thing. Avoid exact 조원/억원 figures in "
        "executive_summary unless they are already provided as display-ready text; "
        "prefer trend-based wording such as '최근 3개년 매출과 순이익은 "
        "개선되었습니다.'\n"
        "- macro_analysis: if macro_context exists, start from its market_regime, "
        "positive_factors, risk_factors, sector_impact, summary, and final_impact. "
        "Then connect exchange rate, US 10Y yield, Nasdaq, WTI, VIX, macro_score, "
        "or macro_score_reasons only when provided. macro_context is "
        "explanation-only and must not change the system score. If data is "
        "unavailable, say so.\n"
        "- fundamental_analysis: this is the accounting_analysis section. Explain "
        "revenue trend, net income trend, FCF quality, debt, margin, 밸류에이션, "
        "moving averages, fundamental_score, and fundamental_score_reasons using "
        "only accounting data. For Korean stocks, describe large revenue/profit/FCF "
        "values in readable 원/조원/억원 units. For US stocks, describe them in "
        "readable dollar units such as $B or $M. Keep markdown source price units "
        "as 원 for Korean stocks and $ for US stocks.\n"
        "For fundamental_analysis, when discussing revenue, net profit, and FCF "
        "trends, it is acceptable to write qualitative trend sentences such as "
        "'매출은 최근 3개년 증가 추세입니다', '순이익은 흑자 전환/개선 "
        "흐름입니다', or 'FCF는 개선되었습니다' without converting every raw "
        "number. If exact values are written, unit conversion must be correct. "
        "Do not write converted financial numbers from chart_data if unsure.\n"
        "- momentum_analysis: this is the news_analysis section. If news_brief "
        "exists, start from its sentiment, momentum_strength, key_positive_factors, "
        "key_risks, price_reflection, summary, final_impact, and evidence_items. "
        "Explain business momentum, positive/negative/neutral issues, and "
        "sentiment reasoning using only provided news titles, sources, dates, "
        "links, snippets, and news_brief. Synthesize the issue; do not merely list "
        "raw results. Do not invent broker names, target prices, article dates, "
        "URLs, or facts. Do not treat news numbers as audited accounting facts.\n"
        "- guru_analysis: this is the youtube_analysis section. If "
        "guru_strategy_context exists, first explain the recent retrieved guru "
        "strategy context, including market view, preferred style, avoid style, "
        "portfolio principle, risk control, and action guide. Then apply that "
        "strategy to the current stock: whether the stock fits preferred style, "
        "conflicts with avoid style, needs price discipline, or only receives "
        "general market/mindset support. If guru_opinion exists, connect the "
        "common context to mention_type, sentiment, confidence, stock_relevance, "
        "opinion_impact, buy_upgrade_signal, price_discipline_note, risk_warning, "
        "summary, and evidence_items. Explain whether the YouTube insight is a "
        "DIRECT stock opinion, SECTOR linkage, MARKET linkage, MINDSET-only "
        "guidance, or NONE/insufficient evidence. If content_type is SPECIFIC or "
        "mention_type is DIRECT, discuss it as stock-related context while avoiding "
        "invented quotes or prices. If content_type or mention_type is MARKET, "
        "MINDSET, RISK, PSYCHOLOGY, or GENERAL, translate it into general "
        "investment behavior, risk control, patience, price confirmation, position "
        "sizing, or split-buy discipline; do not write it as a direct "
        "recommendation for this stock. Do not let guru_strategy_context alone, "
        "MINDSET-only content, or buy_upgrade_signal change the system investment "
        "opinion. Do not claim DB-wide latest broadcasts unless source_window "
        "explicitly proves that scope.\n"
        "- final_conclusion: this is final_judgement plus risk_factors. Explain why "
        "the final opinion is Buy, Hold, Sell, or Strong Buy by connecting macro, "
        "accounting, news, YouTube, price guide, and risk evidence. Include key "
        "downside risks. Explain why the ?? ??? and ??? matter "
        "for entry, patience, split buying, or risk control. Avoid vague filler such "
        "as '종합적으로 긍정적입니다' unless it is backed by concrete evidence.\n"
        "For final_conclusion, do not repeat exact financial figures unless "
        "necessary; focus on trend, profitability, valuation, price discipline, "
        "and risk.\n"
        "- final_conclusion execution guidance: always respect the "
        "system-calculated final_opinion. Connect macro_context, accounting, "
        "news_brief, guru_opinion, price guide, and risk evidence when available. "
        "Separate Buy from execution strategy: if final_opinion is Buy but "
        "target_buy_price is below current_price, say Buy means portfolio "
        "inclusion or constructive direction, not immediate full-position buying; "
        "recommend split entry, pullback entry, and price discipline. If "
        "final_opinion is Hold but guru_opinion is bullish, explain that "
        "guru/company direction may be positive while price, risk, or system "
        "discipline keeps the opinion conservative. If final_opinion is Sell or "
        "Hold due to risks, do not let bullish guru evidence override hard risks "
        "in wording.\n"
        "- chart_data: exactly T-2, T-1, T using accounting revenue, net_income as "
        "net_profit, and fcf raw numeric values. Preserve fields period, revenue, "
        "net_profit, fcf.\n\n"
        "Style constraints: avoid repeating the same sentence across sections, keep "
        "section-specific reasoning, avoid unsupported flourish, and prefer cautious "
        "wording when evidence is weak."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_analysis_structured_output(
    company: str = "",
    analysis_inputs=None,
    final_opinion: str = "Hold",
    target_buy_price=None,
    defense_price=None,
):
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    completion = client.beta.chat.completions.parse(
        model=get_openai_analysis_model(),
        messages=build_analysis_messages(
            company=company,
            analysis_inputs=analysis_inputs,
            final_opinion=final_opinion,
            target_buy_price=target_buy_price,
            defense_price=defense_price,
        ),
        response_format=DirectAnalysisOutput,
    )

    return completion.choices[0].message.parsed
