import os
from crewai.tools import BaseTool
from pydantic import Field
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

class LocalYoutubeSearchTool(BaseTool):
    name: str = "로컬 유튜브 인사이트 검색기"
    description: str = "주알홍쌤의 유튜브 영상이 저장된 로컬 데이터베이스를 검색합니다. 종목명(예: '테슬라', '삼성전자')이나 시장 키워드(예: '시황', '금리', '마인드')를 입력하여 관련된 핵심 발언을 찾아냅니다."

    def _run(self, query: str) -> str:
        # 1. 저장해둔 로컬 DB(chroma_db) 불러오기
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        db_path = "./chroma_db"
        
        if not os.path.exists(db_path):
            return "🚨 로컬 DB가 존재하지 않습니다. 먼저 update_youtube_db.py를 실행하여 DB를 구축하세요."
            
        vector_db = Chroma(persist_directory=db_path, embedding_function=embeddings)
        
        # 2. MMR(Maximal Marginal Relevance) 검색 방식 적용
        # 💡 유사성뿐만 아니라 '다양성'까지 고려하여 중복되지 않은 상위 3개 추출 (반복 발언 필터링)
        docs = vector_db.max_marginal_relevance_search(query, k=3, fetch_k=10)
        
        if not docs:
            return f"'{query}'에 대한 주알홍쌤의 언급을 찾을 수 없습니다."
            
        # 3. 뽑아온 조각들을 하나로 합쳐서 에이전트에게 전달
        formatted_docs = []
        for doc in docs:
            meta_header = f"[📅 {doc.metadata.get('date', '알 수 없음')} 방송 | 🎬 {doc.metadata.get('title', '제목 없음')} | ID: {doc.metadata.get('source', '알 수 없음')}]"
            formatted_docs.append(f"{meta_header}\n{doc.page_content}")
            
        result_text = "\n\n---\n\n".join(formatted_docs)
        return f"[검색 키워드: {query}에 대한 홍쌤의 관련 발언 조각들]\n{result_text}"

def get_guru_youtube_tool():
    """
    CrewAI 에이전트에게 쥐어줄 인스턴스를 반환합니다.
    """
    return LocalYoutubeSearchTool()