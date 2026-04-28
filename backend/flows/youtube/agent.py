from crewai import Agent
from .tool import get_guru_youtube_tool # 툴 파일에서 도구 가져오기

class YoutubeAgent:
    def __init__(self, llm):
        self.llm = llm
        self.youtube_tool = get_guru_youtube_tool() # 🚨 도구 장착!

    def guru_analyst(self):
        return Agent(
            role='유튜브 투자 철학 애널리스트',
            goal='주알홍쌤 채널의 영상을 분석하여 핵심 투자 인사이트와 시장 뷰를 추출',
            backstory='당신은 유튜브 주알홍쌤(홍프로) 채널의 열혈 구독자이자 영상 요약 전문가입니다. 노이즈가 많은 영상 스크립트 속에서 투자에 직결되는 핵심 명언과 시황 관점만 날카롭게 뽑아냅니다.',
            verbose=True,
            tools=[self.youtube_tool],
            llm=self.llm
        )