from schemas.report_state import ReportState


def _set_report_step(state: ReportState | None, step: str):
    if state is not None:
        state["current_step"] = step


def _get_price_unit(ticker: str):
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KRW"
    return "USD"


def _format_price(value, unit):
    if value is None:
        return "N/A"

    if not isinstance(value, (int, float)):
        return "N/A"

    if unit == "KRW":
        return f"{value:,.0f}원"

    return f"${value:,.2f}"


def render_markdown_report(
    ticker: str,
    company: str,
    final_opinion: str,
    final_result,
    current_price,
    target_buy_price,
    defense_price,
    state: ReportState | None = None,
):
    _set_report_step(state, "render_report")
    report_data = final_result.pydantic
    chart_json = final_result.pydantic.model_dump_json(
        include={"chart_data"},
        indent=2,
    )

    price_unit = _get_price_unit(ticker)
    current_price_text = _format_price(current_price, price_unit)
    target_buy_price_text = _format_price(target_buy_price, price_unit)
    defense_price_text = _format_price(defense_price, price_unit)

    if final_opinion in ["Strong Buy", "Buy"]:
        buy_comment = "적정 비중 매수 권고"
    elif final_opinion == "Hold":
        buy_comment = "관망 또는 보유 기준"
    else:
        buy_comment = "신규 매수 비권고"

    md_report = f"""# 📈 {company} 심층 투자 전략 리포트

| 구분 | 가격 정보 | 투자 의견 |
| :--- | :--- | :--- |
| **현재가** | **{current_price_text}** | **{report_data.investment_opinion}** |
| **권장 매수가** | **{target_buy_price_text}** | {buy_comment} |
| **하락 시 방어선/저항선** | **{defense_price_text}** | 분할 매수/대응 |

### 💡 수석 애널리스트 한 줄 결론
> **{report_data.one_line_conclusion}**

### 🎯 3줄 요약 (Executive Summary)
"""

    for line in report_data.executive_summary:
        md_report += f"- {line}\n"

    md_report += f"""
---

## 1. 🌍 매크로 및 시장 환경
{report_data.macro_analysis}

## 2. 📊 펀더멘털 및 퀀트 분석
{report_data.fundamental_analysis}

## 3. 📰 비즈니스 모멘텀 (최신 뉴스)
{report_data.momentum_analysis}

## 4. 📺 구루의 시장관 및 종목 해석
{report_data.guru_analysis}

## 5. 💡 수석 애널리스트 종합 결론
{report_data.final_conclusion}

---

## 📎 실적 차트 데이터
"""

    md_report += "```json\n"
    md_report += chart_json
    md_report += "\n```\n"

    if state is not None:
        state["chart_data"] = final_result.pydantic.model_dump(
            include={"chart_data"},
            mode="json",
        )
        state["final_report"] = {
            "investment_opinion": report_data.investment_opinion,
            "one_line_conclusion": report_data.one_line_conclusion,
            "markdown": md_report,
        }
        state["status"] = "report_generated"

    return md_report
