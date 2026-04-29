from crewai import Task
from pydantic import BaseModel, Field
from typing import Optional, List


class MacroOutput(BaseModel):
    exchange_rate: Optional[float] = Field(description="현재 원/달러 환율")
    us_10y_yield: Optional[float] = Field(description="현재 미국 10년물 국채 금리")
    nasdaq_index: Optional[float] = Field(description="현재 나스닥 지수")
    wti_price: Optional[float] = Field(description="현재 WTI 원유 가격")
    vix_index: Optional[float] = Field(description="현재 VIX 지수")

    exchange_rate_change_1mo: Optional[float] = Field(description="원/달러 환율 1개월 변화율")
    us_10y_yield_change_1mo: Optional[float] = Field(description="미국 10년물 금리 1개월 변화율")
    nasdaq_index_change_1mo: Optional[float] = Field(description="나스닥 1개월 변화율")
    wti_price_change_1mo: Optional[float] = Field(description="WTI 1개월 변화율")
    vix_index_change_1mo: Optional[float] = Field(description="VIX 1개월 변화율")

    risk_warnings: List[str] = Field(description="위험 경고 목록")
    macro_briefing: str = Field(description="거시경제 브리핑")
    is_data_valid: bool = Field(description="모든 지표 정상 수집 여부")
    error: Optional[str] = Field(description="오류 메시지")


class MacroTask:
    def analyze_macro_economy(self, agent):
        return Task(
            description='''
            'Fetch Macro Economy API' 도구를 사용하여 글로벌 거시경제 지표를 가져오세요.

            🚨 핵심 규칙:
            - 도구가 반환하는 JSON 값을 그대로 MacroOutput 스키마에 매핑하세요.
            - 숫자를 임의로 만들거나 수정하지 마세요.
            - 도구 JSON의 null 값은 null 그대로 유지하세요.
            - 도구 JSON의 is_data_valid가 false이면 반드시 is_data_valid를 false로 반환하세요.
            - 시장 점수 계산은 하지 마세요. 이후 main.py의 Python 룰베이스가 처리합니다.
            ''',
            expected_output='구조화된 매크로 JSON',
            agent=agent,
            output_pydantic=MacroOutput,
        )