from crewai import Task
from datetime import datetime
from pydantic import BaseModel, Field


class ResearchOutput(BaseModel):
    sentiment_score: float = Field(description="최신 뉴스 기반 주가 센티먼트 점수, 0.0~100.0, 50은 중립")
    momentum_strength: str = Field(description="단기 뉴스 모멘텀 강도, HIGH/MEDIUM/LOW")
    news_summary: str = Field(description="핵심 뉴스 요약 및 인사이트, 재무 수치 제외")
    is_data_valid: bool = Field(description="실제 최신 뉴스를 정상 수집했는지 여부")


class ResearchTask:
    def collect_news_task(self, agent, company_name):
        today_date = datetime.now().strftime("%Y-%m-%d")

        return Task(
            description=f'''
            오늘({today_date}) 기준으로 {company_name}의 주가 방향성 판단에 필요한 최신 뉴스를 검색하세요.

            🚨 [검색 강제]
            반드시 safe_serper_news_search 도구를 사용하세요.
            검색은 아래 3가지 앵글로 각각 수행하세요.

            1. 매크로 영향:
               "{company_name} 금리 환율 수급 주가 영향 site:hankyung.com OR site:mk.co.kr OR site:infomax.co.kr"

            2. 산업/경쟁사 동향:
               "{company_name} 산업 경쟁사 수급 전망 site:hankyung.com OR site:mk.co.kr OR site:infomax.co.kr"

            3. 실적/목표가/증권사 리포트:
               "{company_name} 목표가 증권사 리포트 실적 전망 site:hankyung.com OR site:mk.co.kr OR site:infomax.co.kr"

            💡 당일 기사가 없다면 최근 1~2주 내 의미 있는 기사만 사용하세요.

            🚨 [도구 결과 검증]
            - 도구 결과 JSON의 is_data_valid가 false이면 해당 검색 결과는 사용하지 마세요.
            - 세 검색 중 최소 1개 이상 유효한 실제 뉴스 결과가 있어야 최종 is_data_valid를 True로 설정하세요.
            - 유효한 뉴스가 하나도 없으면:
              sentiment_score = 50.0
              momentum_strength = "LOW"
              news_summary = "최신 유의미한 뉴스 데이터 수집 실패"
              is_data_valid = False
              로 반환하세요.

            🚨 [재무 수치 사용 금지]
            - 뉴스에 포함된 매출, 영업이익, 순이익, EPS, 영업이익률 등 구체적인 재무 숫자는 news_summary에 쓰지 마세요.
            - 실적 관련 내용은 "어닝 서프라이즈", "수익성 개선", "적자 전환", "실적 우려"처럼 정성 방향성만 쓰세요.
            - 재무 수치는 Accounting 데이터만 최종 리포트에서 사용합니다.

            🚨 [환각 금지]
            - 검색 결과에 없는 기사 제목, URL, 증권사명, 목표가, 수치, 날짜를 만들지 마세요.
            - 출처가 불명확하면 사용하지 마세요.
            - 부족하면 부족하다고 쓰세요.

            🚨 [점수 산정]
            - 매우 긍정적 뉴스 다수: 70~85
            - 긍정 우위: 60~69
            - 중립/혼재: 45~55
            - 부정 우위: 30~44
            - 매우 부정적 뉴스 다수: 15~29
            - 유효 뉴스 없음: 50.0

            🚨 [출력 길이 제한]
            - news_summary는 1200자 이내로 작성하세요.
            - 핵심 뉴스 3개 이하만 요약하세요.
            - 마크다운 표는 사용하지 마세요.
            ''',
            expected_output=f'{company_name} 최신 뉴스 요약 및 센티먼트 점수를 포함한 JSON',
            agent=agent,
            output_pydantic=ResearchOutput,
        )