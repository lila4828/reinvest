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
        "Do not write markdown in field values. The provided investment opinion is "
        "final and must not be changed. Never invent revenue, profit, FCF, prices, "
        "dates, news, YouTube comments, target prices, or analyst claims. Use only "
        "the supplied macro, accounting, research, YouTube, price-guide, and score "
        "inputs. Facts, numbers, prices, scores, chart_data, and final investment "
        "opinion are system-controlled; your role is to synthesize and explain them."
    )

    user_prompt = (
        f"Company: {company}\n"
        f"Investment opinion: {final_opinion}\n"
        f"분할매수 기준가: {target_buy_price_text}\n"
        f"매도 검토가: {defense_price_text}\n\n"
        f"Accounting data:\n{analysis_inputs['accounting']}\n\n"
        f"Macro data:\n{analysis_inputs['macro']}\n\n"
        f"Research data:\n{analysis_inputs['research']}\n\n"
        f"YouTube data:\n{analysis_inputs['youtube']}\n\n"
        "Write the report as a senior investment analyst, not as a generic summary. "
        "Explain the investment opinion using accounting quality, macro pressure or "
        "support, news sentiment, YouTube/guru context, price discipline, and risks. "
        "Do not overuse phrases like '시스템 최종 의견은'. Write for beginner investors "
        "without exposing implementation details.\n\n"
        "Grounding rules:\n"
        "- Use only provided macro, accounting, research, YouTube, current price, "
        "분할매수 기준가, and 매도 검토가 data.\n"
        "- Do not create missing facts, estimates, dates, article details, broker "
        "names, prices, revenue, profit, FCF, scores, target prices, or YouTube quotes.\n"
        "- If data is missing, stale, invalid, or weak, explicitly say the evidence "
        "is limited and keep the interpretation conservative.\n"
        "- News snippets may indicate momentum, but they are not audited financial "
        "statements. Do not use news numbers as accounting facts.\n"
        "- Deterministic Python code controls markdown headings, price table labels, "
        "price units, chart_data, and final investment opinion.\n"
        "- Do not mention KRW conversion for US stocks in markdown source; frontend "
        "rendering handles KRW conversion.\n\n"
        "Price wording and strategy rules:\n"
        "- Never use the old labels '권장 매수가', '하락 시 방어선/저항선', or "
        "'리스크 기준가' in report prose.\n"
        "- Explain target_buy_price only as '분할매수 기준가'. It is a moving-average "
        "based pullback/split-entry reference, not a price that must be bought.\n"
        "- Explain defense_price only as '매도 검토가'. It is a risk-review level "
        "around roughly -30% from current price, not a forced sell order.\n"
        "- Separate investment opinion from entry strategy. Investment opinion is "
        "the stock direction judgement; entry strategy is how cautiously to enter "
        "from the current price.\n"
        "- If the opinion is Buy but current price is above the 분할매수 기준가, say "
        "new entry should wait for a pullback or use split entry. Do not imply "
        "immediate full-position buying.\n"
        "- Prefer plain Korean expressions such as 분할 접근, 보수적 진입, 조정 시 접근, "
        "and 리스크 재점검. Avoid hard buy/sell commands.\n\n"
        "Financial unit conversion safety:\n"
        "- chart_data values are raw KRW numbers for Korean stocks. revenue, "
        "net_profit, and fcf in chart_data are raw 원 values.\n"
        "- 1조원 = 1,000,000,000,000원. 1억원 = 100,000,000원.\n"
        "- If conversion is needed, use value_in_조원 = raw_value / "
        "1,000,000,000,000 and value_in_억원 = raw_value / 100,000,000.\n"
        "- Double-check magnitude before writing financial figures. For example, "
        "44,260,956,000,000원 is about 44.26조원, not 4.43조원.\n"
        "- Do not casually convert raw KRW values into 조원/억원 unless the conversion "
        "is certain. If unsure, prefer qualitative trend wording.\n"
        "- Prefer existing accounting/fundamental summary text if it already "
        "provides interpreted values.\n\n"
        "Structured brief priority:\n"
        "- Macro data may contain macro_context. If macro_context exists, use "
        "market_regime, positive_factors, risk_factors, sector_impact, summary, and "
        "final_impact as explanation context only. Do not recalculate macro_score "
        "and do not invent macro indicators.\n"
        "- Research data may contain news_brief. If news_brief exists, use sentiment, "
        "momentum_strength, key_positive_factors, key_risks, price_reflection, "
        "summary, final_impact, and evidence_items. Do not invent article facts, "
        "broker opinions, URLs, dates, target prices, or full article text.\n"
        "- YouTube data may contain common guru strategy context and per-stock guru "
        "evidence. Use it as supporting context only, not as a standalone reason to "
        "change the final investment opinion.\n\n"
        "Korean wording rules:\n"
        "- Write every prose field in natural Korean. Do not output Chinese or "
        "Japanese characters, mixed-language artifacts, broken encoding text, or raw "
        "internal labels unless they are unavoidable proper nouns.\n"
        "- Translate enum-like labels into natural Korean. Do not expose raw labels "
        "like bearish, low, DIRECT, MARKET, MINDSET, or SPECIFIC in prose.\n"
        "- Do not expose internal field names in prose. Forbidden examples include "
        "guru_opinion, buy_upgrade_signal, price_discipline_note, "
        "guru_strategy_context, sentiment_score, evidence_date, and relevance.\n"
        "- Keep sentences concise and professional. Avoid repeated punctuation, "
        "awkward shorthand, and missing-space negation.\n"
        "- Keep claims measured. Avoid direct commands such as '반드시 매수', '즉시 매도', "
        "or '무조건 진입'.\n\n"
        "Macro section rules:\n"
        "- macro_analysis must be 3 sentences by default and never more than 5 "
        "sentences.\n"
        "- Do not list every macro indicator. Mention only the factors with the "
        "largest direct impact on this company.\n"
        "- Do not repeat the same macro figures across executive_summary, "
        "macro_analysis, and final_conclusion.\n"
        "- Avoid long generic macro commentary that would apply equally to every "
        "stock.\n\n"
        "Guru section rules:\n"
        "- The markdown heading is controlled by the renderer and remains "
        "'## 4. 📺 구루의 시장관 및 종목 해석'. Do not include markdown headings in "
        "field values.\n"
        "- In guru_analysis, convert internal evidence into natural Korean. For "
        "example, explain that guru materials are judged by direct stock mention, "
        "freshness, price discipline, and risk-control comments.\n"
        "- If YouTube material does not clearly provide buy price, target price, or "
        "stop-loss price, do not replace those with system price levels.\n"
        "- YouTube insight is a supporting reference. Do not write it as the sole "
        "basis for the final investment opinion.\n\n"
        "Field requirements:\n"
        "- investment_opinion: exactly the investment opinion above. Do not override "
        "it. Ensure all sections are consistent with it while discussing risks "
        "honestly.\n"
        "- one_line_conclusion: one concise Korean sentence, preferably within 40 "
        "Korean characters, with the strongest evidence-based reason.\n"
        "- executive_summary: exactly 3 items. Each item must include a specific "
        "reason from accounting, macro, news, YouTube, price, or risk. Avoid making "
        "all 3 bullets repeat the same point. Avoid exact 조원/억원 figures unless "
        "they are already display-ready.\n"
        "- macro_analysis: follow the Macro section rules. Focus on direct impact "
        "and avoid broad indicator lists.\n"
        "- fundamental_analysis: explain revenue trend, net income trend, FCF "
        "quality, debt, margin, valuation, moving averages, fundamental_score, and "
        "fundamental_score_reasons using only accounting data. Mention "
        "분할매수 기준가 and 매도 검토가 only as price-discipline references when useful.\n"
        "- momentum_analysis: explain business momentum and sentiment using only "
        "provided news titles, sources, dates, links, snippets, and news_brief. "
        "Synthesize the issue; do not merely list raw results.\n"
        "- guru_analysis: follow the Guru section rules. Discuss whether the YouTube "
        "material is direct stock evidence, sector context, market context, or "
        "mindset/risk-control guidance without exposing raw field names.\n"
        "- final_conclusion: connect accounting, macro, news, YouTube, price "
        "discipline, and downside risks. Separate investment opinion from entry "
        "strategy. If the opinion is Buy but the current price is above the "
        "분할매수 기준가, explain that Buy means constructive direction or portfolio "
        "inclusion, while entry still requires split buying, pullback confirmation, "
        "and price discipline. If the opinion is Hold, explain why new buying should "
        "remain conservative. If risks dominate, prioritize risk review and position "
        "management.\n"
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
