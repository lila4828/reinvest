import os
from dotenv import load_dotenv
from crewai import Crew, Process, LLM

from flows.research.agents import ResearchAgents
from flows.research.tasks import ResearchTasks
from flows.analysis.agents import AnalysisAgents
from flows.analysis.tasks import AnalysisTasks
from flows.accounting.agents import AccountingAgents
from flows.accounting.tasks import AccountingTasks

# 1. 환경 변수 로드
load_dotenv()

def run_financial_crew():
    # 2-1. 가벼운 업무용 모델 (리서치, 재무 수집)
    fast_llm = LLM(
        model="gemini/gemini-2.5-flash", # 최신 속도 중점 모델
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.3,
        stream=True
    )

    # 2-2. 깊은 사고용 모델 (최종 투자 전략 분석)
    smart_llm = LLM(
        model="gemini/gemini-2.5-pro", # 추론 능력이 더 뛰어난 모델
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.5, # 분석의 창의성을 위해 리서치보다 살짝 높게 설정
        stream=True
    )

    # 1. 팀 매니저들 소집
    res_admin = ResearchAgents(fast_llm)      #검색 팀장
    res_tasks = ResearchTasks()
    acc_admin = AccountingAgents(fast_llm)    #재무 팀장
    acc_tasks = AccountingTasks()
    ana_admin = AnalysisAgents(smart_llm)      #분석 팀장
    ana_tasks = AnalysisTasks()


    # 4. 각 폴더의 모듈에서 에이전트 소환
    researcher_agent = res_admin.news_researcher()
    accounting_agent = acc_admin.financial_analyst()
    analyst_agent = ana_admin.investment_analyst()

    # 5. 각 폴더의 모듈에서 업무(Task) 할당
    # 리서치 업무 생성
    task_research = res_tasks.collect_news_task(researcher_agent)
    # 재무 업무 생성
    task_accounting = acc_tasks.analyze_financial_statements(accounting_agent)
    # 분석 업무 생성 (리서치 결과를 context로 넘겨받음)
    task_analysis = ana_tasks.report_writing_task(analyst_agent, [task_research, task_accounting])

    # 6. 크루(전체 팀) 구성
    financial_crew = Crew(
        agents=[researcher_agent, accounting_agent, analyst_agent],
        tasks=[task_research, task_accounting, task_analysis],
        process=Process.sequential, # 리서치 완료 후 분석 진행
        max_rpm=2, # 분당 요청 횟수를 제한하여 503 에러 방지
        verbose=True,
        cache=True
    )

    # 7. 팀 가동 (Kickoff)
    print("🚀 [시스템] 금융 리서치 및 분석 팀을 가동합니다...")
    result = financial_crew.kickoff()
    return result

if __name__ == "__main__":
    final_result = run_financial_crew()
    
    print("\n" + "="*50)
    print("📊 [최종 투자 분석 리포트]")
    print("="*50)
    print(final_result)