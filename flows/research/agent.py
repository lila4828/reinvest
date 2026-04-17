from crewai import Agent
from .tool import search_tool 
class ResearchAgent:
    def __init__(self, llm):
        self.llm = llm

    def news_researcher(self):
        return Agent(
            role='금융 시장 리서처',
            goal='최신 뉴스에서 기업의 핵심 데이터를 수집합니다.',
            backstory='웹상의 방대한 정보 중 노이즈를 제거하고 팩트만 골라냅니다.',
            tools=[search_tool],
            llm=self.llm,
            verbose=True
        )