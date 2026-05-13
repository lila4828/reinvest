# Legacy CrewAI reference kept for migration history; active runtime does not import this module.
from crewai import Agent
from .tool import search_tool


class ResearchAgent:
    def __init__(self, llm):
        self.llm = llm

    def news_researcher(self):
        return Agent(
            role="시니어 글로벌 금융 리서치 애널리스트",
            goal="기업의 주가 펀더멘털에 직접적인 영향을 미치는 고품질 핵심 경제 기사와 기관 분석 데이터를 발굴합니다.",
            backstory="""
            당신은 월스트리트와 여의도에서 활동하는 탑티어 리서처입니다.
            단순 가십성 기사, 개인 블로그, 출처가 불명확한 글은 배제합니다.
            반드시 검색 도구가 반환한 실제 결과만 사용하며, 검색 결과가 부족하면 부족하다고 명시합니다.
            뉴스 요약에서는 재무 에이전트와 충돌할 수 있는 매출, 영업이익, 순이익 등 구체적인 실적 숫자를 사용하지 않습니다.
            """,
            tools=[search_tool],
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
        )
