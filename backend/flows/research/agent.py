from crewai import Agent
from .tool import search_tool 

class ResearchAgent:
    def __init__(self, llm):
        self.llm = llm

    def news_researcher(self):
        return Agent(
            role='시니어 글로벌 금융 리서치 애널리스트',
            goal='{company_name}의 주가 펀더멘털에 직접적인 영향을 미치는 고품질의 핵심 경제 기사와 기관 분석 데이터를 발굴합니다.',
            backstory='''당신은 월스트리트와 여의도에서 활동하는 탑티어 리서처입니다. 
            단순 가십성 기사나 개인 블로그 글은 철저히 배제합니다. 
            검색 품질을 높이기 위해 구글 검색 시 반드시 'site:hankyung.com OR site:mk.co.kr OR site:infomaxs.co.kr' 와 같은 검색 연산자를 사용하여 신뢰할 수 있는 메이저 경제 매체로 출처를 제한하는 능력이 있습니다.''',
            tools=[search_tool],
            llm=self.llm,
            verbose=True
        )