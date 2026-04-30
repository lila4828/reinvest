from crewai import Task
from pydantic import BaseModel, Field


class YoutubeOutput(BaseModel):
    guru_sentiment_score: float = Field(
        description="유튜버의 투자 스탠스 점수. SPECIFIC이고 최신 종목 직접 발언일 때만 적극 반영, MARKET/MINDSET/RISK는 50.0 중립"
    )
    key_strategy: str = Field(
        description="핵심 투자 전략. 예: 추격매수 경계, 분할 접근, 관망, 수급 확인, 리스크 관리"
    )
    content_type: str = Field(
        description="영상 성격. SPECIFIC, MARKET, MINDSET, RISK, PSYCHOLOGY, N/A 중 하나"
    )
    insight_date: str = Field(
        description="가장 최신으로 활용한 유튜브 인사이트 날짜. 알 수 없으면 N/A"
    )
    freshness_level: str = Field(
        description="인사이트 신선도. FRESH, RECENT, OLD, STALE, UNKNOWN, N/A 중 하나"
    )
    mindset_summary: str = Field(
        description="투자 마인드/심리 관리 관점 요약"
    )
    market_principle: str = Field(
        description="시장 대응 원칙, 수급/심리/매크로 해석 요약"
    )
    risk_control: str = Field(
        description="리스크 관리, 비중 조절, 분할매수/관망/추격매수 경계 원칙 요약"
    )
    guru_insight_details: str = Field(
        description="selected_docs의 날짜, 제목, 핵심 발언을 바탕으로 작성한 상세 인사이트"
    )
    is_data_valid: bool = Field(
        description="실제 유의미한 영상 스크립트 수집 여부"
    )


class YoutubeTask:
    def extract_guru_view(self, agent, company_name):
        return Task(
            description=f'''
            'local_youtube_search_tool' 도구를 사용하여 {company_name} 관련 유튜브 인사이트를 검색하세요.

            이 유튜브 데이터의 핵심 목적은 목표가, 매수가, 매도가를 찾는 것이 아닙니다.
            핵심 목적은 다음을 추출하는 것입니다.

            - 투자 마인드
            - 시장 대응 원칙
            - 수급/심리 해석
            - 종목을 바라보는 관점
            - 추격매수 경계
            - 분할매수/관망/리스크 관리 철학

            🚨 [도구 결과 해석 규칙]
            - 도구는 JSON 형태로 결과를 반환합니다.
            - selected_docs 안에 있는 실제 스크립트만 근거로 사용하세요.
            - selected_docs가 비어 있거나 error가 있으면 is_data_valid를 False로 설정하세요.
            - 도구의 content_type_hint를 content_type 판단의 1차 기준으로 사용하세요.
            - 도구의 freshness_level, latest_date, latest_days_old를 반드시 반영하세요.
            - selected_docs의 date, days_old, title, search_type, theme_hint, content를 활용하세요.

            🚨 [content_type 구분]
            - SPECIFIC:
              해당 종목을 직접 언급한 영상/스크립트입니다.
              해당 종목에 대한 구루의 시선으로 활용할 수 있습니다.

            - MARKET:
              시장 시황, 금리, 환율, 나스닥, 코스피/코스닥, 수급 등 시장 대응 자료입니다.
              {company_name} 개별 호재/악재로 해석하지 마세요.
              대신 현재 종목에 적용 가능한 시장 대응 원칙으로 정리하세요.

            - MINDSET:
              투자 마인드, 심리 관리, 기다림, 원칙, 탐욕/공포 통제에 관한 자료입니다.
              매수/매도 추천이 아니라 투자자의 행동 통제 원칙으로 정리하세요.

            - RISK:
              현금 비중, 손절, 분할매수, 관망, 추격매수 경계, 비중 조절 등 리스크 관리 자료입니다.
              가격 예측이 아니라 리스크 관리 원칙으로 정리하세요.

            - PSYCHOLOGY:
              수급, 심리, 차트 확인, 뉴스보다 가격 확인 등 시장 심리 해석 자료입니다.
              종목의 현재 가격 위치와 투자자 심리 해석에 활용할 수 있도록 정리하세요.

            - N/A:
              유의미한 영상 스크립트가 없는 경우입니다.

            🚨 [Plan A / Plan B 해석]
            - content_type_hint가 SPECIFIC이면 해당 종목에 대한 직접 분석으로 간주하세요.
            - content_type_hint가 MARKET, MINDSET, RISK, PSYCHOLOGY이면 해당 종목 직접 추천이 아니라 구루의 투자 철학/시장 대응 원칙입니다.
            - MARKET, MINDSET, RISK, PSYCHOLOGY 결과를 절대 {company_name} 개별 호재나 악재로 해석하지 마세요.
            - 대신 "이 구루 관점을 {company_name}에 적용하면 어떤 투자 태도가 적절한가"를 정리하세요.

            🚨 [날짜/신선도 반영]
            - insight_date에는 도구의 latest_date를 사용하세요.
            - freshness_level에는 도구의 freshness_level을 그대로 사용하세요.
            - selected_docs의 days_old가 7일 이내이면 FRESH로 해석하세요.
            - 30일 이내이면 RECENT로 해석하세요.
            - 90일 이내이면 OLD로 해석하세요.
            - 90일 초과이면 STALE로 해석하세요.
            - 오래된 자료일수록 현재 매수/매도 판단보다는 투자 원칙 참고용으로만 사용하세요.
            - 날짜가 알 수 없으면 freshness_level은 UNKNOWN 또는 N/A로 두고, 최신 발언처럼 쓰지 마세요.

            🚨 [점수 산정 규칙]
            - content_type이 MARKET, MINDSET, RISK, PSYCHOLOGY이면 guru_sentiment_score는 반드시 50.0으로 고정하세요.
            - content_type이 N/A이면 guru_sentiment_score는 반드시 50.0으로 고정하고 is_data_valid를 False로 설정하세요.
            - content_type이 SPECIFIC이어도 selected_docs의 days_old가 모두 30일 초과라면 guru_sentiment_score는 50.0으로 고정하세요.
            - content_type이 SPECIFIC이고 7일 이내 종목 직접 분석이 있으면 발언 뉘앙스에 따라 0.0~100.0 점수를 부여하세요.
            - 7일 초과 30일 이내 SPECIFIC이면 과도한 점수를 피하고 35~65 범위 안에서만 부여하세요.
            - 점수는 구루 발언의 매수/매도 성향을 반영하되, 스크립트에 없는 확신을 만들지 마세요.

            🚨 [출력 필드 작성 규칙]
            - key_strategy:
              selected_docs에서 가장 반복적으로 등장하는 핵심 대응 전략을 짧게 쓰세요.
              예: "추격매수보다 가격 확인", "분할 접근과 현금 비중 유지", "뉴스보다 수급 확인", "기다림과 원칙 준수"

            - mindset_summary:
              투자 마인드, 심리 통제, 탐욕/공포 관리, 기다림, 원칙에 대한 내용을 요약하세요.
              관련 내용이 없으면 "직접적인 투자 마인드 발언은 제한적"이라고 쓰세요.

            - market_principle:
              시장 시황, 수급, 금리/환율, 지수 흐름, 뉴스와 가격의 관계에 대한 구루의 대응 원칙을 요약하세요.
              관련 내용이 없으면 "직접적인 시장 대응 원칙은 제한적"이라고 쓰세요.

            - risk_control:
              추격매수 경계, 분할매수, 관망, 현금 비중, 손절/방어, 비중 조절 관련 내용을 요약하세요.
              관련 내용이 없으면 "직접적인 리스크 관리 발언은 제한적"이라고 쓰세요.

            - guru_insight_details:
              selected_docs의 날짜, 제목, 핵심 발언을 바탕으로 상세히 작성하세요.
              반드시 날짜와 제목을 최소 1개 이상 언급하세요.
              단, 날짜나 제목이 알 수 없음이면 억지로 만들지 마세요.
              개조식보다는 최종 분석 에이전트가 이해하기 쉬운 서술형으로 작성하세요.

            🚨 [환각 방지]
            - 스크립트에 없는 주가, 상승률, 목표가, 거래량, 실적 수치를 만들지 마세요.
            - 유튜버가 실제로 말하지 않은 매수/매도 추천을 만들지 마세요.
            - 유튜버가 직접 "{company_name}을 사라/팔라"고 말하지 않았다면 그렇게 단정하지 마세요.
            - MARKET/MINDSET/RISK/PSYCHOLOGY 자료를 {company_name}의 직접 호재/악재로 쓰지 마세요.
            - 근거가 약하면 "직접 종목 언급은 제한적"이라고 명시하세요.

            🚨 [출력 규칙]
            - JSON/Pydantic 스키마에 맞는 값만 반환하세요.
            - 마크다운 표는 사용하지 마세요.
            - 각 필드는 너무 길게 쓰지 말고 핵심만 담으세요.
            - guru_insight_details는 1200자 이내로 작성하세요.
            ''',
            expected_output='주알홍쌤 유튜브 인사이트를 투자 마인드/시장 대응 원칙/리스크 관리 관점으로 구조화한 JSON',
            agent=agent,
            output_pydantic=YoutubeOutput,
        )