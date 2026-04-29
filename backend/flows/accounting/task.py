from crewai import Task
from pydantic import BaseModel, Field
from typing import List, Optional


class AccountingOutput(BaseModel):
    ticker: str = Field(description="티커")
    current_price: Optional[float] = Field(description="현재 주가")
    per: Optional[float] = Field(description="PER")
    pbr: Optional[float] = Field(description="PBR")
    dividend_yield: Optional[float] = Field(description="배당 수익률(%)")
    ma_60: Optional[float] = Field(description="60일 이동평균선")
    ma_200: Optional[float] = Field(description="200일 이동평균선")
    ma_350: Optional[float] = Field(description="350일 이동평균선")
    ma_500: Optional[float] = Field(description="500일 이동평균선")
    ma_999: Optional[float] = Field(description="999일 이동평균선")
    roe_raw: Optional[float] = Field(description="ROE 원본 수치(%)")
    roe_label: str = Field(description="ROE 평가 라벨")
    revenue: List[float] = Field(description="최근 3개년 매출 배열, 과거 -> 최근 순서")
    net_income: List[float] = Field(description="최근 3개년 순이익 배열, 과거 -> 최근 순서")
    fcf: List[float] = Field(description="최근 3개년 FCF 배열, 과거 -> 최근 순서")
    debt_to_equity: Optional[float] = Field(description="부채비율")
    operating_margin: Optional[float] = Field(description="영업이익률(%)")
    sector: str = Field(description="섹터")
    industry: str = Field(description="산업")
    financial_summary: str = Field(description="재무 상태 요약")
    is_data_valid: bool = Field(description="3개년 재무 데이터 정상 수집 여부")
    error: Optional[str] = Field(description="오류 메시지")


class AccountingTask:
    def analyze_financial_statements(self, agent, company_name, ticker):
        return Task(
            description=f'''
            'Fetch Financial Data API' 도구를 사용하여 {company_name}({ticker})의 재무 데이터를 가져오세요.

            🚨 핵심 규칙:
            - 도구가 반환하는 JSON 값을 그대로 AccountingOutput 스키마에 매핑하세요.
            - revenue, net_income, fcf 배열 순서는 반드시 과거 -> 최근 순서입니다.
            - 숫자를 새로 계산하거나 임의로 보정하지 마세요.
            - 도구 JSON의 null 값은 null 그대로 유지하세요.
            - 도구 JSON의 is_data_valid가 false이면 반드시 is_data_valid를 false로 반환하세요.
            - PASS/FAIL 판단은 하지 마세요. 이후 main.py의 Python 룰베이스가 처리합니다.
            ''',
            expected_output=f'{company_name}의 구조화된 재무 JSON',
            agent=agent,
            output_pydantic=AccountingOutput,
        )