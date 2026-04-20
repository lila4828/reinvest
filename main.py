import os
from dotenv import load_dotenv
from crewai import Crew, Process, LLM

from flows.research.agent import ResearchAgent
from flows.research.task import ResearchTask
from flows.analysis.agent import AnalysisAgent
from flows.analysis.task import AnalysisTask
from flows.accounting.agent import AccountingAgent
from flows.accounting.task import AccountingTask
from flows.macro.agent import MacroAgent
from flows.macro.task import MacroTask

# 0. 환경 변수 로드
load_dotenv()

def run_financial_crew():    
    # 1-1. 가벼운 업무용 모델 (리서치, 재무 수집)
    fast_llm = LLM(
        model="gpt-4o-mini",
        api_key=os.getenv('OPENAI_API_KEY'),
        temperature=0.3,
        stream=True
    )
    # 1-2. 깊은 사고용 모델 (최종 투자 전략 분석)
    smart_llm = LLM(
        model="gpt-4o",
        api_key=os.getenv('OPENAI_API_KEY'),
        temperature=0.5,
        stream=True
    )

    # ---------------------------------------------------------
    # 2. 글로벌 거시경제 분석 (전체 프로세스 시작 전 딱 한 번 수행)
    # ---------------------------------------------------------
    print(f"\n🌍 [0단계] 글로벌 거시경제 지표 분석을 시작합니다...")
    macro_admin = MacroAgent(fast_llm)
    macro_tasks = MacroTask()
    
    macro_economist = macro_admin.macro_economist()
    task_macro = macro_tasks.analyze_macro_economy(macro_economist)

    macro_crew = Crew(
        agents=[macro_economist],
        tasks=[task_macro],
        verbose=False
    )
    macro_result = macro_crew.kickoff()
    print(f"✅ 매크로 분석 완료: 환율/금리 상황 파악 성공.")

    # ---------------------------------------------------------
    # 3. 다중 종목 스캔 루프 (옵션 C: 3개 종목 연속 처리)
    # ---------------------------------------------------------
    stock_pool = [
        ("005930.KS", "삼성전자"),        # (기존) "PASS (주의)" 받고 리포트까지 나오는지 확인
        ("0009K0.KQ", "에임드바이오"),    # 💡 (테스트용) 1년 미만 신규 상장! "FAIL" 컷오프 확인
        ("000660.KS", "SK하이닉스"),      # (기존) 정상 통과 후 리포트 확인
    ]

    # 모든 종목의 최종 결과를 모아둘 리스트
    all_reports = []

    print("\n🏭 [시스템] 다중 종목 재무 필터링 및 분석 공장을 가동합니다...")

    for target_ticker, target_company in stock_pool:
        print(f"\n{'='*60}")
        print(f"🎯 [시스템] 타겟 종목 스캔: {target_company} ({target_ticker})")
        print(f"{'='*60}")

        # 에이전트 소집
        res_admin = ResearchAgent(fast_llm)      
        res_tasks = ResearchTask()
        acc_admin = AccountingAgent(fast_llm)    
        acc_tasks = AccountingTask()
        ana_admin = AnalysisAgent(smart_llm)      
        ana_tasks = AnalysisTask()

        # [1단계] 재무 및 상장 검토 (Filter)
        print(f"📊 [1단계] 재무 건전성 및 999일 이평선 검토 중...")
        accounting_agent = acc_admin.financial_analyst()
        task_accounting = acc_tasks.analyze_financial_statements(accounting_agent, target_company, target_ticker)

        financial_crew = Crew(
            agents=[accounting_agent],
            tasks=[task_accounting],
            verbose=False
        )
        acc_result = financial_crew.kickoff()

        # FAIL 조건 체크
        if "FAIL" in acc_result.raw or "부적격" in acc_result.raw:
            skip_msg = f"🚫 [분석 중단] {target_company}: 기준 미달\n{acc_result.raw}"
            print(skip_msg)
            all_reports.append(skip_msg)
            continue

        print(f"✅ [1단계 통과] {target_company} 합격.")

        # [2단계] 뉴스 리서치 및 종합 분석
        # 💡 매크로 결과(macro_result)를 시니어 분석가에게 Context로 함께 전달합니다.
        researcher_agent = res_admin.news_researcher()
        analyst_agent = ana_admin.investment_analyst()

        task_research = res_tasks.collect_news_task(researcher_agent, target_company)
        
        # 💡 분석 태스크에 재무결과(acc_result)와 매크로결과(macro_result)를 모두 태워 보냅니다.
        task_analysis = ana_tasks.report_writing_task(
            analyst_agent, 
            target_company, 
            acc_result.raw,           # 재무/이평선/배당 데이터
            macro_result.raw,         # 환율/금리/나스닥 데이터
            [task_research]           # 최신 뉴스 데이터
        )

        analysis_crew = Crew(
            agents=[researcher_agent, analyst_agent],
            tasks=[task_research, task_analysis],
            process=Process.sequential,
            verbose=True
        )
        
        print(f"📰 [2단계] {target_company} 종합 리포트 생성 중...")
        final_result = analysis_crew.kickoff()
        all_reports.append(f"📈 [{target_company} 최종 리포트]\n{final_result.raw}")

    return "\n\n" + "★"*60 + "\n\n".join(all_reports)

if __name__ == "__main__":
    final_output = run_financial_crew()
    print("\n\n" + "="*60)
    print("🏆 [전체 분석 결과]")
    print("="*60)
    print(final_output)