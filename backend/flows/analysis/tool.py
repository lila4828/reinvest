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

    return [
        {
            "role": "system",
            "content": (
                "You are a senior investment analyst writing a disciplined Korean "
                "stock report. Return only structured data matching the schema. "
                "Do not write markdown in field values. The provided system "
                "investment opinion is final and must not be changed. Never invent "
                "revenue, profit, FCF, prices, dates, news, YouTube comments, target "
                "prices, or analyst claims. Use only the supplied macro, accounting, "
                "research, YouTube, price-guide, and system-score inputs. If a value "
                "is missing, say it is unavailable and interpret cautiously."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Company: {company}\n"
                f"System investment opinion: {final_opinion}\n"
                f"Target buy price: {target_buy_price_text}\n"
                f"Defense price: {defense_price_text}\n\n"
                f"Accounting data:\n{analysis_inputs['accounting']}\n\n"
                f"Macro data:\n{analysis_inputs['macro']}\n\n"
                f"Research data:\n{analysis_inputs['research']}\n\n"
                f"YouTube data:\n{analysis_inputs['youtube']}\n\n"
                "Write the report as a senior investment analyst, not as a generic "
                "summary. Explain why the final opinion follows from the system "
                "score, accounting quality, macro pressure/support, news sentiment, "
                "and guru insight. Distinguish the system-calculated opinion from "
                "YouTube/guru insight; YouTube is supporting context, not a source "
                "of target prices or direct buy/sell claims unless the provided "
                "content explicitly says so.\n\n"
                "Field requirements:\n"
                "- investment_opinion: exactly the system investment opinion above. "
                "Do not override it.\n"
                "- one_line_conclusion: one concise Korean sentence, preferably "
                "within 40 Korean characters, with the final opinion and core reason.\n"
                "- executive_summary: exactly 3 items. Each item must include a "
                "specific reason from macro, accounting, news, YouTube, price, or risk.\n"
                "- macro_analysis: discuss market environment, exchange rate, US "
                "10Y yield, Nasdaq, WTI, VIX, and whether they pressure or support "
                "the stock. If data is unavailable, say so.\n"
                "- fundamental_analysis: this is the accounting_analysis section. "
                "Use only accounting data for revenue, net profit, FCF, PER, PBR, "
                "ROE, moving averages, debt, margin, fundamental_score, and price "
                "guide reasoning. Do not use news numbers as financial facts. "
                "For Korean stocks, describe large revenue/profit/FCF values in "
                "readable 원/조원/억원 units. For US stocks, describe them in "
                "readable dollar units such as $B or $M. Keep markdown source "
                "price units as 원 for Korean stocks and $ for US stocks.\n"
                "- momentum_analysis: this is the news_analysis section. Explain "
                "business momentum and sentiment using only provided news titles, "
                "sources, dates, links, and snippets. Do not invent broker names, "
                "target prices, article dates, URLs, or facts.\n"
                "- guru_analysis: this is the youtube_analysis section. Explain "
                "whether the YouTube insight is stock-specific or a general market, "
                "mindset, psychology, or risk-management principle. For general "
                "principles, translate them into cautious investment behavior; do "
                "not treat them as direct stock recommendation.\n"
                "- final_conclusion: this is final_judgement plus risk_factors. "
                "Explain why the final opinion is Buy, Hold, Sell, or Strong Buy "
                "using the supplied data. Include key downside risks and why the "
                "target buy price and defense price matter. Avoid vague filler such "
                "as '종합적으로 긍정적입니다' unless backed by evidence.\n"
                "- chart_data: exactly T-2, T-1, T using accounting revenue, "
                "net_income as net_profit, and fcf raw numeric values. Preserve "
                "fields period, revenue, net_profit, fcf.\n\n"
                "Style constraints: avoid repeating the same sentence across "
                "sections, keep section-specific reasoning, and prefer cautious "
                "wording when evidence is weak."
            ),
        },
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
