# Legacy CrewAI reference kept for migration history; active runtime does not import this module.
from crewai import Agent
from flows.accounting.tool import fetch_financial_data


class AccountingAgent:
    def __init__(self, llm):
        self.llm = llm

    def financial_analyst(self):
        return Agent(
            role="재무 데이터 구조화 요원",
            goal="Fetch Financial Data API가 반환한 JSON 재무 데이터를 AccountingOutput 스키마에 정확히 매핑합니다.",
            backstory="""
            당신은 재무 데이터를 해석하거나 평가하는 애널리스트가 아니라, 데이터 구조화 담당자입니다.
            PASS/FAIL 판단, 투자 적격성 판단, 점수 계산은 절대 하지 않습니다.
            도구가 반환한 JSON의 숫자, null, 배열 순서를 그대로 유지하여 출력 스키마에 맞게 정리합니다.
            """,
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[fetch_financial_data],
        )
