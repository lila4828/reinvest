import os
from typing import List

from pydantic import BaseModel, Field


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
        "Korean wording rules:\n"
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
        "all 3 bullets say the same thing.\n"
        "- macro_analysis: discuss market environment, exchange rate, US 10Y yield, "
        "Nasdaq, WTI, VIX, and whether they pressure or support the stock. Connect "
        "macro_score or macro_score_reasons when provided. If data is unavailable, "
        "say so.\n"
        "- fundamental_analysis: this is the accounting_analysis section. Explain "
        "revenue trend, net income trend, FCF quality, debt, margin, 밸류에이션, "
        "moving averages, fundamental_score, and fundamental_score_reasons using "
        "only accounting data. For Korean stocks, describe large revenue/profit/FCF "
        "values in readable 원/조원/억원 units. For US stocks, describe them in "
        "readable dollar units such as $B or $M. Keep markdown source price units "
        "as 원 for Korean stocks and $ for US stocks.\n"
        "- momentum_analysis: this is the news_analysis section. Explain business "
        "momentum, positive/negative/neutral issues, and sentiment reasoning using "
        "only provided news titles, sources, dates, links, and snippets. Synthesize "
        "the issue; do not merely list raw results. Do not invent broker names, "
        "target prices, article dates, URLs, or facts.\n"
        "- guru_analysis: this is the youtube_analysis section. Explain whether the "
        "YouTube insight is stock-specific or a general market, mindset, psychology, "
        "or risk-control principle. If content_type is SPECIFIC, discuss it as "
        "stock-related context while avoiding invented quotes or prices. If "
        "content_type is MARKET, MINDSET, RISK, or PSYCHOLOGY, translate it into "
        "general investment behavior, risk control, patience, price confirmation, "
        "position sizing, or split-buy discipline; do not write it as a direct "
        "recommendation for this stock.\n"
        "- final_conclusion: this is final_judgement plus risk_factors. Explain why "
        "the final opinion is Buy, Hold, Sell, or Strong Buy by connecting macro, "
        "accounting, news, YouTube, price guide, and risk evidence. Include key "
        "downside risks. Explain why the ?? ??? and ??? matter "
        "for entry, patience, split buying, or risk control. Avoid vague filler such "
        "as '종합적으로 긍정적입니다' unless it is backed by concrete evidence.\n"
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
        model=os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4o-mini"),
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
