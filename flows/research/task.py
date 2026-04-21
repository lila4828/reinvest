from crewai import Task
from datetime import datetime

class ResearchTask:
    def collect_news_task(self, agent, company_name):
        # 💡 AI가 날짜를 헷갈리지 않도록 오늘 날짜를 정확히 주입합니다.
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        return Task(
            description=f'''
            오늘({today_date}) 기준으로 {company_name}의 주가 방향성을 판단하기 위한 가장 중요한 최신 뉴스 3개를 수집하세요.
            💡 (주의: 당일 작성된 기사가 없다면, 최근 1~2주일 내에 보도된 가장 의미 있는 최신 기사를 활용해도 무방합니다.)
            아래 3가지 앵글로 각각 검색어를 다르게 하여 정보를 찾아야 합니다:
            
            1. 매크로 충격: 미국 기준금리/국채금리 또는 환율 변동이 {company_name}의 비즈니스에 미치는 영향을 다룬 심층 분석 기사
            2. 산업/경쟁사 동향: {company_name}의 주력 비즈니스(예: 반도체, 바이오 등) 수급 트렌드 및 경쟁사 비교
            3. 실적/목표가: 최근 한 달 내 주요 증권사들이 발표한 {company_name} 목표가 변경 리포트나 실적 전망 기사

            💡 [검색 및 작성 주의사항]
            - 검색 도구를 사용할 때 검색어에 'site:hankyung.com' 또는 'site:mk.co.kr' 등을 포함하여 메이저 경제 언론사로만 대상을 좁히세요.
            - 🚨 절대로 URL(링크)을 스스로 지어내지 마세요. 도구가 반환한 결과에 있는 실제 원본 출처 링크만 사용해야 합니다.
            ''',
            expected_output=f'{company_name} 관련 3가지 앵글(매크로, 산업동향, 실적전망)에 맞춘 핵심 뉴스 요약 및 원본 출처 링크',
            agent=agent
        )