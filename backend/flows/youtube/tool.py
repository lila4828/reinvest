import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from crewai.tools import BaseTool
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings


def _safe_parse_date(date_text: str):
    if not date_text:
        return None

    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_text[:10], fmt).date()
        except Exception:
            continue

    return None


def _days_old(date_text: str):
    parsed = _safe_parse_date(date_text)
    if not parsed:
        return None

    return (datetime.now().date() - parsed).days


def _normalize_doc(doc, query: str, search_type: str):
    metadata = doc.metadata or {}

    date_text = metadata.get("date", "알 수 없음")
    days_old = _days_old(date_text)

    return {
        "query": query,
        "search_type": search_type,
        "date": date_text,
        "days_old": days_old,
        "title": metadata.get("title", "제목 없음"),
        "source": metadata.get("source", "알 수 없음"),
        "content": doc.page_content,
    }


class LocalYoutubeSearchTool(BaseTool):
    name: str = "local_youtube_search_tool"
    description: str = (
        "주알홍쌤 유튜브 로컬 벡터 DB 검색 도구입니다. "
        "종목명 또는 시장 키워드를 입력하면 관련 발언을 검색하고, "
        "종목 직접 검색 결과가 약할 경우 자동으로 시황/투자마인드 Plan B 검색을 수행합니다."
    )

    db_path: str = "./chroma_db"
    _vector_db: Optional[Chroma] = None

    def _get_vector_db(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY 누락: OpenAIEmbeddings 사용 불가")

        if not os.path.exists(self.db_path):
            raise RuntimeError(
                f"유튜브 Chroma DB 경로 없음: {self.db_path}. "
                "먼저 유튜브 DB 업데이트 파이프라인을 실행하세요."
            )

        if self._vector_db is None:
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            self._vector_db = Chroma(
                persist_directory=self.db_path,
                embedding_function=embeddings,
            )

        return self._vector_db

    def _search(self, query: str, search_type: str, k: int = 12):
        vector_db = self._get_vector_db()
        docs = vector_db.similarity_search(query, k=k)

        normalized = [
            _normalize_doc(doc, query=query, search_type=search_type)
            for doc in docs
        ]

        normalized.sort(
            key=lambda x: (
                x["days_old"] if x["days_old"] is not None else 99999
            )
        )

        return normalized

    def _is_specific_result_useful(self, docs: List[Dict[str, Any]], company_name: str):
        if not docs:
            return False

        company_lower = company_name.lower()

        for doc in docs[:6]:
            text = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
            if company_lower in text:
                return True

        return False

    def _format_result(
        self,
        company_name: str,
        specific_docs: List[Dict[str, Any]],
        fallback_docs: List[Dict[str, Any]],
        content_type: str,
        is_specific_useful: bool,
    ):
        selected_docs = specific_docs[:6] if is_specific_useful else fallback_docs[:6]

        result = {
            "is_data_valid": len(selected_docs) > 0,
            "error": None,
            "company_name": company_name,
            "content_type_hint": content_type,
            "is_specific_useful": is_specific_useful,
            "specific_result_count": len(specific_docs),
            "fallback_result_count": len(fallback_docs),
            "selected_docs": selected_docs,
            "scoring_hint": {
                "rule": (
                    "content_type_hint가 SPECIFIC이고 selected_docs 중 7일 이내 종목 직접 분석이 있을 때만 "
                    "guru_sentiment_score를 적극적으로 부여하세요. "
                    "MARKET 또는 MINDSET이면 guru_sentiment_score는 50.0 중립으로 고정하세요."
                )
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    def _run(self, query: str) -> str:
        try:
            company_name = query.strip()

            if not company_name:
                return json.dumps(
                    {
                        "is_data_valid": False,
                        "error": "검색어 없음",
                        "content_type_hint": "N/A",
                        "selected_docs": [],
                    },
                    ensure_ascii=False,
                )

            # Plan A: 종목 직접 검색
            specific_docs = self._search(company_name, search_type="SPECIFIC", k=30)
            is_specific_useful = self._is_specific_result_useful(
                specific_docs,
                company_name,
            )

            # 종목 직접 결과가 유효하면 SPECIFIC
            if is_specific_useful:
                return self._format_result(
                    company_name=company_name,
                    specific_docs=specific_docs,
                    fallback_docs=[],
                    content_type="SPECIFIC",
                    is_specific_useful=True,
                )

            # Plan B: 시장/마인드셋 fallback 검색
            fallback_queries = [
                "시황 금리 환율 투자 전략",
                "시장 심리 투자 마인드 대응 전략",
                "주식시장 대응 현금 비중 리스크 관리",
            ]

            fallback_docs = []
            for fallback_query in fallback_queries:
                fallback_docs.extend(
                    self._search(fallback_query, search_type="MARKET", k=10)
                )

            fallback_docs.sort(
                key=lambda x: (
                    x["days_old"] if x["days_old"] is not None else 99999
                )
            )

            return self._format_result(
                company_name=company_name,
                specific_docs=specific_docs,
                fallback_docs=fallback_docs,
                content_type="MARKET",
                is_specific_useful=False,
            )

        except Exception as e:
            return json.dumps(
                {
                    "is_data_valid": False,
                    "error": str(e),
                    "content_type_hint": "N/A",
                    "selected_docs": [],
                },
                ensure_ascii=False,
                indent=2,
            )


def get_guru_youtube_tool():
    return LocalYoutubeSearchTool()