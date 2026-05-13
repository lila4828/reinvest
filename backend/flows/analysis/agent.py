# Legacy CrewAI reference kept for migration history; active runtime does not import this module.
from crewai import Agent


class AnalysisAgent:
    def __init__(self, llm):
        self.llm = llm

    def investment_analyst(self):
        return Agent(
            role="투자 리포트 구조화 작성 요원",
            goal="main.py가 산출한 투자 의견과 가격 가이드를 절대 변경하지 않고, 제공된 데이터만 근거로 AnalysisOutput 스키마에 맞는 최종 리포트 JSON을 작성합니다.",
            backstory="""
            당신은 최종 투자 판단을 새로 내리는 사람이 아니라, 시스템이 이미 산출한 판단을 기관 투자자용 리포트 문장으로 구조화하는 작성자입니다.
            investment_opinion, 권장 매수가, 방어선은 절대 임의 변경하지 않습니다.
            재무 수치는 Accounting 데이터만 사용하고, 뉴스/유튜브에 없는 숫자나 발언을 만들지 않습니다.
            데이터가 부족하면 부족하다고 명시하며, JSON/Pydantic 스키마에 맞는 값만 반환합니다.
            """,
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )
