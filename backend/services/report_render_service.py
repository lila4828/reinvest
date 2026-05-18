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


def _build_entry_strategy(final_opinion, current_price, target_buy_price):
    if not (
        isinstance(current_price, (int, float))
        and current_price > 0
        and isinstance(target_buy_price, (int, float))
        and target_buy_price > 0
    ):
        return "가격 기준 일부가 확인되지 않아 진입 전략은 보수적으로 해석해야 합니다."

    opinion = str(final_opinion or "").strip().lower()
    near_threshold = 1.03

    if opinion in ["strong buy", "buy"]:
        if current_price > target_buy_price * near_threshold:
            return "현재가는 분할매수 기준가보다 높아, 신규 진입은 조정 시 분할 접근이 적절합니다."

        return "분할매수 기준가에 근접한 구간으로, 무리한 일괄 매수보다 분할 접근이 적절합니다."

    if opinion == "hold":
        return "기존 보유자는 유지 관점으로 보되, 신규 매수는 분할매수 기준가 부근까지 조정을 확인하는 편이 보수적입니다."

    return "신규 진입보다 보유 비중과 하방 리스크를 우선 점검하는 구간입니다."


def render_failed_markdown_report(company: str, fail_reason: str):
    reason = str(fail_reason or "분석 중단 사유를 확인할 수 없습니다.").strip()

    return f"""# ⚠️ {company} 분석 중단 리포트

| 항목 | 내용 |
| :--- | :--- |
| **상태** | 분석 중단 |
| **중단 사유** | {reason} |
| **처리 결과** | 하드 리스크 조건에 해당하여 정식 투자 리포트를 생성하지 않았습니다. |

## 해석
이 결과는 투자 부적합 확정이 아니라, 현재 시스템의 보수적 필터 기준을 통과하지 못했다는 의미입니다.

## 다음 확인 포인트
- 최근 FCF 개선 여부
- 일회성 투자 지출 여부
- 영업현금흐름과 순이익의 괴리
"""


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

    price_unit = _get_price_unit(ticker)
    current_price_text = _format_price(current_price, price_unit)
    target_buy_price_text = _format_price(target_buy_price, price_unit)
    defense_price_text = _format_price(defense_price, price_unit)
    entry_strategy = _build_entry_strategy(
        final_opinion,
        current_price,
        target_buy_price,
    )

    md_report = f"""# 📊 {company} 주식 투자 전략 리포트

| 구분 | 가격 정보 |
| :--- | :--- |
| **현재가** | **{current_price_text}** |
| **분할매수 기준가** | **{target_buy_price_text}** |
| **매도 검토가** | **{defense_price_text}** |

### 🧭 투자 판단 요약

- **투자의견:** {report_data.investment_opinion}
- **진입 전략:** {entry_strategy}
- **분할매수 기준가:** {target_buy_price_text}
- **매도 검토가:** {defense_price_text} 부근은 현재가 대비 약 -30% 구간의 리스크 재점검 기준입니다.

### 💡 수석 애널리스트 한 줄 결론
> **{report_data.one_line_conclusion}**

### 📝 3줄 요약 (Executive Summary)
"""

    for line in report_data.executive_summary:
        md_report += f"- {line}\n"

    md_report += f"""
---

## 1. 📈 매크로 및 시장 환경
{report_data.macro_analysis}

## 2. 🧾 펀더멘털 및 가격 분석
{report_data.fundamental_analysis}

## 3. 📰 비즈니스 모멘텀 (최신 뉴스)
{report_data.momentum_analysis}

## 4. 📺 구루의 시장관 및 종목 해석
{report_data.guru_analysis}

## 5. 💡 수석 애널리스트 종합 결론
{report_data.final_conclusion}
"""

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
