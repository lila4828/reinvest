# Legacy CrewAI reference kept for migration history; active runtime does not import this module.
from crewai import Task
from pydantic import BaseModel, Field
from typing import List


class ChartData(BaseModel):
    period: str = Field(description="예: T-2, T-1, T")
    revenue: float = Field(description="매출")
    net_profit: float = Field(description="순이익")
    fcf: float = Field(description="잉여현금흐름(FCF)")


class AnalysisOutput(BaseModel):
    investment_opinion: str = Field(description="최종 투자 의견, 시스템 산출값 그대로 사용")
    one_line_conclusion: str = Field(description="수석 애널리스트 한 줄 결론, 40자 이내")
    executive_summary: List[str] = Field(description="정확히 3개 항목")
    macro_analysis: str = Field(description="매크로 및 시장 환경 분석, 700자 이내")
    fundamental_analysis: str = Field(description="펀더멘털 및 퀀트 분석, 900자 이내")
    momentum_analysis: str = Field(description="비즈니스 모멘텀 분석, 700자 이내")
    guru_analysis: str = Field(description="구루의 시선 분석, 800자 이내")
    final_conclusion: str = Field(description="수석 애널리스트 종합 결론, 900자 이내")
    chart_data: List[ChartData] = Field(description="최근 3개년 실적 차트 데이터, T-2/T-1/T 순서")


class AnalysisTask:
    def report_writing_task(
        self,
        agent,
        company_name,
        accounting_data,
        macro_data,
        news_data,
        youtube_data,
        final_opinion,
        target_buy_price,
        defense_price,
    ):
        target_buy_price_text = f"{target_buy_price:,.2f}" if isinstance(target_buy_price, (int, float)) else "N/A"
        defense_price_text = f"{defense_price:,.2f}" if isinstance(defense_price, (int, float)) else "N/A"

        return Task(
            description=f'''
            당신은 최종 결정권자인 여의도 탑티어 수석 애널리스트입니다.
            아래 제공된 압축 데이터를 기반으로 {company_name}의 최종 투자 분석 JSON을 작성하세요.

            [입력 데이터]
            1. 거시경제 시황(Macro):
            {macro_data}

            2. 재무 팩트(Accounting):
            {accounting_data}

            3. 최신 뉴스(Research):
            {news_data}

            4. 구루 인사이트(YouTube):
            {youtube_data}

            🚨 [절대 규칙]
            1. investment_opinion은 시스템 산출값 **{final_opinion}**을 반드시 그대로 사용하세요.
               - Strong Buy, Buy, Hold, Sell 중 하나를 임의 변경하지 마세요.
               - 본문과 결론도 이 의견과 충돌하지 않게 작성하세요.
               - 예: investment_opinion이 Buy이면 최종 결론을 Sell/회피처럼 쓰지 마세요.
               - 단, 리스크는 별도 문장으로 균형 있게 언급하세요.

            2. 시스템 산출 가격 가이드:
               - 권장 매수가: {target_buy_price_text}
               - 하락 시 방어선/저항선: {defense_price_text}
               - 가격이 N/A이면 가격 전략을 억지로 만들지 말고 데이터 부족이라고 쓰세요.

            3. 재무 수치 근거:
               - 실적 수치, PER, PBR, ROE, 이동평균선은 반드시 Accounting 데이터만 사용하세요.
               - 뉴스에 나온 매출/이익 숫자는 사용하지 마세요.
               - 입력 데이터의 revenue, net_income, fcf 배열은 과거 -> 최근 순서이며, 이를 ChartData의 revenue, net_profit, fcf 필드에 각각 정확히 매핑하세요.
               - 본문에 재무 수치를 쓸 때는 원본 숫자를 그대로 쓰지 말고 보기 쉬운 단위로 변환하세요.
               - 한국 종목은 매출, 순이익, FCF를 조원/억원 단위로 변환해 서술하세요.
                 예: 333605938000000.0 → 약 333.6조원
                 예: 4859947610.0 → 약 48.6억원
               - 미국 종목은 매출, 순이익, FCF를 B/M 달러 단위로 변환해 서술하세요.
                 예: 94827000000.0 → 약 $94.8B
                 예: 3794000000.0 → 약 $3.8B
               - PER, PBR, ROE, 부채비율, 영업이익률, 이동평균선, 현재가는 원본 수치에 가깝게 사용하되 소수점은 과도하게 길게 쓰지 마세요.
                 예: PER 5.5500317 → PER 5.55배
                 예: ROE 10.78 → ROE 10.78%
                 예: current_price 226000.0 → 226,000원
               - chart_data는 반드시 다음 순서로 만드세요:
                 T-2 = 배열[0]
                 T-1 = 배열[1]
                 T = 배열[2]
               - chart_data 배열에는 Accounting 데이터의 원본 float 숫자를 그대로 넣으세요.

            4. 유튜브 데이터 해석:
               - 유튜브 데이터는 목표가, 매수가, 매도가를 산출하는 근거가 아닙니다.
               - 유튜브 데이터는 투자 마인드, 시장 대응 원칙, 수급/심리 해석, 종목을 바라보는 관점, 추격매수 경계, 분할매수/관망/리스크 관리 철학으로 사용하세요.
               - YouTube 입력에 포함된 content_type, insight_date, freshness_level, mindset_summary, market_principle, risk_control, guru_insight_details를 반드시 참고하세요.

               - content_type이 SPECIFIC이면:
                 해당 종목에 대한 직접적인 시선이나 투자 관점으로 해석하세요.
                 단, 스크립트에 없는 목표가, 매수가, 상승률, 실적 수치, 추천 발언은 만들지 마세요.
                 freshness_level이 OLD 또는 STALE이면 현재 매수/매도 판단보다는 참고 의견으로만 다루세요.

               - content_type이 MARKET이면:
                 개별 종목 추천으로 해석하지 마세요.
                 시장 시황, 금리, 환율, 지수, 수급 변화에 대한 대응 원칙으로 해석하세요.
                 현재 종목의 재무 상태, 가격 위치, 이동평균선, 뉴스 모멘텀과 연결해 "어떤 태도로 대응해야 하는가"를 서술하세요.

               - content_type이 MINDSET이면:
                 매수/매도 판단이 아니라 투자자의 행동 통제, 기다림, 원칙 준수, 탐욕/공포 관리 관점으로 해석하세요.
                 좋은 기업과 좋은 매수 가격을 구분해야 한다는 식의 투자 태도로 풀어 쓰세요.

               - content_type이 RISK이면:
                 현금 비중, 분할매수, 관망, 손절/방어, 추격매수 경계, 비중 조절 원칙으로 해석하세요.
                 현재가가 권장 매수가보다 높거나 주요 이평선과 괴리가 크면 추격매수 경계와 가격 확인 원칙을 강조하세요.

               - content_type이 PSYCHOLOGY이면:
                 수급, 투자 심리, 차트 확인, 뉴스보다 가격 확인 원칙으로 해석하세요.
                 뉴스가 좋아도 실제 가격·수급·이평선 확인이 필요하다는 관점으로 연결하세요.

               - content_type이 N/A이거나 is_data_valid가 false이면:
                 구루 분석에는 "유의미한 직접 발언은 없으며, 별도 구루 근거는 제한적"이라고 쓰세요.

               - guru_analysis는 단순히 "직접 언급 없음"으로 끝내지 마세요.
                 MARKET/MINDSET/RISK/PSYCHOLOGY 자료가 있으면, 개별 호재/악재로 단정하지 않는 범위에서 반드시 현재 종목의 대응 원칙으로 번역하세요.
                 예: "해외 증시 강세를 국내 개별주에 기계적으로 대입하지 말 것", "뉴스보다 가격과 수급 확인이 우선", "좋은 기업과 좋은 매수 가격은 다르다", "추격매수보다 분할 접근과 관망이 적절하다"처럼 서술하세요.

            5. 출력 길이 제한:
               - executive_summary는 정확히 3개만 작성하세요.
               - 각 분석 필드는 짧고 밀도 있게 작성하세요.
               - 불필요한 미사여구 금지.
               - 마크다운 문법 금지.
               - 표 금지.
               - JSON/Pydantic 스키마에 맞는 값만 반환하세요.

            6. 환각 방지:
               - 입력 데이터에 없는 숫자, 목표가, 상승률, 기사 제목, 발언을 만들지 마세요.
               - YouTube 스크립트에 없는 구루 발언을 만들지 마세요.
               - MARKET/MINDSET/RISK/PSYCHOLOGY 자료를 {company_name}의 직접 추천이나 직접 호재/악재로 쓰지 마세요.
               - 모르는 내용은 데이터 부족으로 명시하세요.
            ''',
            expected_output=f'{company_name}에 대한 구조화된 투자 분석 JSON',
            agent=agent,
            output_pydantic=AnalysisOutput,
        )
