from crewai import Agent
from .tool import get_guru_youtube_tool


class YoutubeAgent:
    def __init__(self, llm):
        self.llm = llm
        self.youtube_tool = get_guru_youtube_tool()

    def guru_analyst(self):
        return Agent(
            role="유튜브 스크립트 구조화 요원",
            goal="local_youtube_search_tool이 반환한 JSON 검색 결과를 YoutubeOutput 스키마에 정확히 매핑합니다.",
            backstory="""
            당신은 유튜브 내용을 자유롭게 추측하는 분석가가 아니라, 검색된 스크립트 기반의 구조화 담당자입니다.
            selected_docs에 존재하는 날짜, 제목, 발언 내용만 사용합니다.
            SPECIFIC, MARKET, MINDSET, N/A 구분을 엄격히 지키며, MARKET 데이터를 개별 종목 호재/악재로 해석하지 않습니다.
            스크립트에 없는 주가, 목표가, 상승률, 거래량, 유튜버 발언은 절대 만들지 않습니다.
            """,
            verbose=True,
            tools=[self.youtube_tool],
            llm=self.llm,
            allow_delegation=False,
        )