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
            검색은 아래 5가지 앵글로 각각 수행하세요.

            1. 일반 최신 뉴스:
            "{company_name} 최신 뉴스 주가 전망"

            2. 주가/수급/투자심리:
            "{company_name} 주가 수급 투자심리 기관 외국인"

            3. 실적/증권사 리포트:
            "{company_name} 실적 전망 목표가 증권사 리포트"

            4. 산업/경쟁사/섹터 이슈:
            "{company_name} 산업 경쟁사 시장점유율 수요 전망"

            5. 글로벌/영문 뉴스:
            "{company_name} stock news earnings analyst rating outlook"

            💡 검색 결과가 부족하면 아래 보조 검색어도 사용할 수 있습니다.
            - "{company_name} 주가 전망"
            - "{company_name} 최근 이슈"
            - "{company_name} 투자 의견"
            - "{company_name} earnings guidance outlook"
            - "{company_name} sector outlook"

            💡 당일 기사가 없다면 최근 1~2주 내 의미 있는 기사만 사용하세요.
            단, 최근 1~2주 결과가 부족한 경우에는 30일 이내의 기사까지 참고할 수 있습니다.
            30일 초과 기사는 단기 모멘텀 점수에는 강하게 반영하지 마세요.

            🚨 [도구 결과 검증]
            - 도구 결과 JSON의 is_data_valid가 false이면 해당 검색 결과는 사용하지 마세요.
            - 도구 결과 JSON의 results 배열에 title 또는 snippet이 1개 이상 있으면 유효 뉴스 후보로 간주하세요.
            - 단, title과 snippet이 {company_name}와 명확히 무관하면 제외하세요.
            - 다섯 검색 중 최소 1개 이상 유효한 실제 뉴스 결과가 있어야 최종 is_data_valid를 True로 설정하세요.
            - 유효한 뉴스가 하나도 없으면:
              sentiment_score = 50.0
              momentum_strength = "LOW"
              news_summary = "최신 유의미한 뉴스 데이터 수집 실패"
              is_data_valid = False
              로 반환하세요.

            🚨 [뉴스 사용 규칙]
            - 반드시 도구의 results 배열에 포함된 title, source, date, link, snippet만 근거로 사용하세요.
            - news_summary에는 핵심 뉴스 1~3개만 요약하세요.
            - 각 뉴스는 가능하면 출처와 날짜를 함께 언급하세요.
            - link가 URL 없음이면 링크를 억지로 만들지 마세요.
            - 같은 내용의 중복 기사는 하나로 합쳐서 요약하세요.
            - 단순 주가 등락 기사, 광고성 기사, 개인 블로그성 내용은 핵심 근거에서 제외하세요.

            🚨 [재무 수치 사용 금지]
            - 뉴스에 포함된 매출, 영업이익, 순이익, EPS, 영업이익률, 목표주가 등 구체적인 숫자는 news_summary에 쓰지 마세요.
            - 실적 관련 내용은 "어닝 서프라이즈", "수익성 개선", "적자 전환", "실적 우려", "목표가 상향", "목표가 하향"처럼 정성 방향성만 쓰세요.
            - 재무 수치는 Accounting 데이터만 최종 리포트에서 사용합니다.
            - 뉴스의 숫자가 Accounting 데이터와 충돌할 가능성이 있으면 숫자는 반드시 제외하고 방향성만 서술하세요.

            🚨 [환각 금지]
            - 검색 결과에 없는 기사 제목, URL, 증권사명, 목표가, 수치, 날짜를 만들지 마세요.
            - 출처가 불명확하면 사용하지 마세요.
            - title/source/date/link/snippet에 없는 내용을 추정하지 마세요.
            - 부족하면 부족하다고 쓰세요.

            🚨 [점수 산정]
            - 매우 긍정적 뉴스 다수: 70~85
            - 긍정 우위: 60~69
            - 중립/혼재: 45~55
            - 부정 우위: 30~44
            - 매우 부정적 뉴스 다수: 15~29
            - 유효 뉴스 없음: 50.0

            🚨 [momentum_strength 기준]
            - HIGH: 최근 1~2주 내 기업에 직접적인 호재/악재가 여러 개 있고 방향성이 뚜렷한 경우
            - MEDIUM: 유효 뉴스는 있으나 긍정/부정이 혼재하거나 영향이 제한적인 경우
            - LOW: 뉴스가 부족하거나, 오래됐거나, 기업 직접 영향이 약한 경우

            🚨 [출력 길이 제한]
            - news_summary는 1200자 이내로 작성하세요.
            - 핵심 뉴스 3개 이하만 요약하세요.
            - 마크다운 표는 사용하지 마세요.
            - JSON/Pydantic 스키마에 맞는 값만 반환하세요.
            ''',
            expected_output=f'{company_name} 최신 뉴스 요약 및 센티먼트 점수를 포함한 JSON',
            agent=agent,
            output_pydantic=ResearchOutput,
        )