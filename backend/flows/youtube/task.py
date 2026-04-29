from crewai import Task
from pydantic import BaseModel, Field


class YoutubeOutput(BaseModel):
    guru_sentiment_score: float = Field(description="유튜버의 투자 스탠스 점수 (0.0 ~ 100.0, 50은 중립)")
    key_strategy: str = Field(description="핵심 투자 전략")
    content_type: str = Field(description="영상 성격 (SPECIFIC, MARKET, MINDSET, N/A)")
    guru_insight_details: str = Field(description="유튜버 발언 기반 상세 인사이트")
    is_data_valid: bool = Field(description="실제 유의미한 영상 스크립트 수집 여부")


class YoutubeTask:
    def extract_guru_view(self, agent, company_name):
        return Task(
            description=f'''
            'local_youtube_search_tool' 도구를 사용하여 {company_name} 관련 유튜브 인사이트를 검색하세요.

            🚨 [도구 결과 해석 규칙]
            - 도구는 JSON 형태로 결과를 반환합니다.
            - selected_docs 안에 있는 실제 스크립트만 근거로 사용하세요.
            - selected_docs가 비어 있거나 error가 있으면 is_data_valid를 False로 설정하세요.
            - 도구의 content_type_hint를 content_type 판단의 1차 기준으로 사용하세요.

            🚨 [Plan A / Plan B 구분]
            - content_type_hint가 SPECIFIC이면 해당 종목에 대한 직접 분석으로 간주하세요.
            - content_type_hint가 MARKET이면 해당 종목 직접 분석이 아니라 시장 시황/투자 마인드 fallback입니다.
            - MARKET 결과를 절대 {company_name} 개별 호재나 악재로 해석하지 마세요.
            - MARKET 결과는 오직 시장 대응 전략, 리스크 관리, 현금 비중, 매수 타이밍 참고 자료로만 서술하세요.

            🚨 [점수 산정 규칙]
            - content_type_hint가 MARKET이면 guru_sentiment_score는 반드시 50.0으로 고정하세요.
            - content_type_hint가 N/A이면 guru_sentiment_score는 반드시 50.0으로 고정하고 is_data_valid를 False로 설정하세요.
            - content_type_hint가 SPECIFIC이어도 selected_docs의 days_old가 모두 30일 초과라면 guru_sentiment_score는 50.0으로 고정하세요.
            - content_type_hint가 SPECIFIC이고 7일 이내 종목 직접 분석이 있으면 발언 뉘앙스에 따라 0.0~100.0 점수를 부여하세요.
            - 7일 초과 30일 이내 SPECIFIC이면 과도한 점수를 피하고 35~65 범위 안에서만 부여하세요.

            🚨 [환각 방지]
            - 스크립트에 없는 주가, 상승률, 목표가, 거래량을 만들지 마세요.
            - 유튜버가 실제로 말한 표현, 비유, 숫자만 사용하세요.
            - 근거가 약하면 "직접 종목 언급은 제한적"이라고 명시하세요.

            🚨 [출력 규칙]
            - guru_insight_details에는 selected_docs의 날짜, 제목, 핵심 발언을 바탕으로 상세히 작성하세요.
            - 개조식보다는 최종 분석 에이전트가 이해하기 쉬운 서술형으로 작성하세요.
            ''',
            expected_output='주알홍쌤 유튜브 인사이트를 구조화한 JSON',
            agent=agent,
            output_pydantic=YoutubeOutput,
        )