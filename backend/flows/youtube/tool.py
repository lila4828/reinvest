import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


def _safe_parse_date(date_text: str):
    if not date_text:
        return None

    cleaned_text = date_text.replace(" ", "")
    match = re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", cleaned_text)
    if not match:
        return None

    cleaned_date = match.group(0)

    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned_date, fmt).date()
        except Exception:
            continue

    return None


def _days_old(date_text: str):
    parsed = _safe_parse_date(date_text)
    if not parsed:
        return None

    return (datetime.now().date() - parsed).days


def _detect_content_theme(text: str):
    """
    스크립트 내용 기반으로 영상/문서의 성격을 보조 분류한다.
    최종 content_type_hint는 Plan A/Plan B 로직에서 결정하지만,
    selected_docs마다 theme_hint를 붙여 AnalysisAgent가 더 잘 해석하게 한다.
    """
    if not text:
        return "UNKNOWN"

    normalized = text.replace(" ", "").lower()

    mindset_keywords = [
        "마인드",
        "심리",
        "멘탈",
        "탐욕",
        "공포",
        "조급",
        "흔들",
        "원칙",
        "습관",
        "기다림",
        "인내",
        "확신",
        "욕심",
        "공포매도",
        "패닉셀",
        "뇌동매매",
        "감정",
        "평정심",
        "멘탈관리",
    ]

    risk_keywords = [
        "리스크",
        "손절",
        "비중",
        "현금",
        "분할",
        "분할매수",
        "추격매수",
        "불타기",
        "물타기",
        "관망",
        "대응",
        "방어",
        "확인",
        "매수타이밍",
        "진입",
        "대기",
        "눌림목",
        "손실관리",
        "비중조절",
    ]

    market_keywords = [
        "시황",
        "시장",
        "나스닥",
        "금리",
        "환율",
        "수급",
        "외국인",
        "기관",
        "코스피",
        "코스닥",
        "반도체",
        "2차전지",
    ]

    if any(keyword in normalized for keyword in risk_keywords):
        return "RISK"

    if any(keyword in normalized for keyword in mindset_keywords):
        return "MINDSET"

    if any(keyword in normalized for keyword in market_keywords):
        return "MARKET"

    return "GENERAL"


def _normalize_doc(doc, query: str, search_type: str):
    metadata = doc.metadata or {}

    date_text = metadata.get("date", "알 수 없음")
    days_old = _days_old(date_text)

    title = metadata.get("title", "제목 없음")
    source = metadata.get("source", "알 수 없음")
    content = doc.page_content or ""

    theme_text = f"{title} {content}"
    theme_hint = _detect_content_theme(theme_text)

    return {
        "query": query,
        "search_type": search_type,
        "theme_hint": theme_hint,
        "date": date_text,
        "days_old": days_old,
        "title": title,
        "source": source,
        "content": content,
    }


class LocalYoutubeSearchTool:
    name: str = "local_youtube_search_tool"
    description: str = (
        "주알홍쌤 유튜브 로컬 벡터 DB 검색 도구입니다. "
        "종목명 또는 시장/투자 마인드 키워드를 입력하면 관련 발언을 검색합니다. "
        "종목 직접 검색 결과가 약할 경우 시장 대응, 투자 마인드, 수급/심리, "
        "리스크 관리 원칙 중심의 Plan B 검색을 수행합니다."
    )

    db_path: str = "./chroma_db"

    def __init__(self):
        self._vector_db: Any = None

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

        company_clean = company_name.replace(" ", "").lower()

        for doc in docs[:8]:
            text = f"{doc.get('title', '')} {doc.get('content', '')}"
            text_clean = text.replace(" ", "").lower()

            if company_clean in text_clean:
                return True

        return False

    def _dedupe_docs(self, docs: List[Dict[str, Any]]):
        deduped = []
        seen = set()

        for doc in docs:
            key = (
                doc.get("title", ""),
                doc.get("date", ""),
                str(doc.get("content", ""))[:200],
            )

            if key in seen:
                continue

            seen.add(key)
            deduped.append(doc)

        return deduped

    def _build_fallback_docs(self):
        """
        종목 직접 분석이 약할 때 사용할 구루 철학/시장 대응용 검색.
        MARKET만이 아니라 투자 마인드, 수급/심리, 리스크 관리 원칙을 함께 수집한다.
        """
        fallback_queries = [
            {
                "query": "시황 금리 환율 투자 전략",
                "search_type": "MARKET",
            },
            {
                "query": "시장 심리 투자 마인드 대응 전략",
                "search_type": "MINDSET",
            },
            {
                "query": "주식시장 대응 현금 비중 리스크 관리",
                "search_type": "RISK",
            },
            {
                "query": "추격매수 분할매수 관망 리스크 관리",
                "search_type": "RISK",
            },
            {
                "query": "수급 심리 차트 뉴스보다 가격 확인",
                "search_type": "PSYCHOLOGY",
            },
            {
                "query": "좋은 기업 좋은 매수 가격 투자 원칙",
                "search_type": "MINDSET",
            },
            {
                "query": "뇌동매매 공포 탐욕 투자 원칙",
                "search_type": "MINDSET",
            },
            {
                "query": "기다림 인내 분할매수 투자 마인드",
                "search_type": "MINDSET",
            },
        ]

        fallback_docs = []

        for item in fallback_queries:
            docs = self._search(
                item["query"],
                search_type=item["search_type"],
                k=8,
            )
            fallback_docs.extend(docs)

        fallback_docs = self._dedupe_docs(fallback_docs)

        fallback_docs.sort(
            key=lambda x: (
                x["days_old"] if x["days_old"] is not None else 99999
            )
        )

        return fallback_docs

    def _summarize_freshness(self, selected_docs: List[Dict[str, Any]]):
        if not selected_docs:
            return {
                "freshness_level": "N/A",
                "latest_date": "N/A",
                "latest_days_old": None,
            }

        valid_days = [
            doc.get("days_old")
            for doc in selected_docs
            if isinstance(doc.get("days_old"), int)
        ]

        latest_doc = selected_docs[0]
        latest_date = latest_doc.get("date", "알 수 없음")
        latest_days_old = latest_doc.get("days_old")

        if not valid_days:
            freshness_level = "UNKNOWN"
        else:
            min_days = min(valid_days)

            if min_days <= 7:
                freshness_level = "FRESH"
            elif min_days <= 30:
                freshness_level = "RECENT"
            elif min_days <= 90:
                freshness_level = "OLD"
            else:
                freshness_level = "STALE"

        return {
            "freshness_level": freshness_level,
            "latest_date": latest_date,
            "latest_days_old": latest_days_old,
        }

    def _infer_fallback_content_type(self, fallback_docs: List[Dict[str, Any]]):
        """
        Plan B 결과 중 어떤 성격이 강한지 판단한다.
        MINDSET/RISK/PSYCHOLOGY가 많으면 MARKET보다 투자 마인드 자료로 넘긴다.
        """
        if not fallback_docs:
            return "N/A"

        type_counts = {
            "MARKET": 0,
            "MINDSET": 0,
            "RISK": 0,
            "PSYCHOLOGY": 0,
            "GENERAL": 0,
        }

        for doc in fallback_docs[:8]:
            search_type = doc.get("search_type", "GENERAL")
            theme_hint = doc.get("theme_hint", "GENERAL")

            if search_type in type_counts:
                type_counts[search_type] += 1

            if theme_hint in type_counts:
                type_counts[theme_hint] += 1

        mindset_score = (
            type_counts["MINDSET"]
            + type_counts["RISK"]
            + type_counts["PSYCHOLOGY"]
        )

        market_score = type_counts["MARKET"]

        if mindset_score > market_score:
            return "MINDSET"

        return "MARKET"

    def _format_result(
        self,
        company_name: str,
        specific_docs: List[Dict[str, Any]],
        fallback_docs: List[Dict[str, Any]],
        content_type: str,
        is_specific_useful: bool,
    ):
        selected_docs = specific_docs[:6] if is_specific_useful else fallback_docs[:8]
        freshness = self._summarize_freshness(selected_docs)

        result = {
            "is_data_valid": len(selected_docs) > 0,
            "error": None,
            "company_name": company_name,
            "content_type_hint": content_type,
            "is_specific_useful": is_specific_useful,
            "specific_result_count": len(specific_docs),
            "fallback_result_count": len(fallback_docs),
            "freshness_level": freshness["freshness_level"],
            "latest_date": freshness["latest_date"],
            "latest_days_old": freshness["latest_days_old"],
            "selected_docs": selected_docs,
            "interpretation_guide": {
                "SPECIFIC": (
                    "해당 종목을 직접 언급한 자료입니다. "
                    "종목에 대한 관점으로 활용하되, 스크립트에 없는 목표가/매수가/상승률은 만들지 마세요."
                ),
                "MARKET": (
                    "시장 시황/수급/매크로 대응 자료입니다. "
                    "개별 종목 추천으로 해석하지 말고, 현재 종목의 가격 위치와 리스크 관리 원칙에 적용하세요."
                ),
                "MINDSET": (
                    "투자 마인드/심리 관리/대응 원칙 자료입니다. "
                    "매수·매도 추천이 아니라 추격매수 경계, 분할 접근, 관망, 비중 조절 원칙으로 해석하세요."
                ),
                "RISK": (
                    "리스크 관리/현금 비중/분할매수/손절/관망 관련 자료입니다. "
                    "가격 예측이 아니라 포지션 관리와 방어 원칙으로 해석하세요."
                ),
                "PSYCHOLOGY": (
                    "수급/심리/차트 확인/뉴스보다 가격 확인 관련 자료입니다. "
                    "시장 참여자의 심리와 실제 가격 확인 원칙으로 해석하세요."
                ),
                "N/A": "유의미한 구루 인사이트가 없습니다.",
            },
            "scoring_hint": {
                "rule": (
                    "content_type_hint가 SPECIFIC이고 selected_docs 중 7일 이내 종목 직접 분석이 있을 때만 "
                    "guru_sentiment_score를 적극적으로 부여하세요. "
                    "MARKET, MINDSET, RISK, PSYCHOLOGY이면 guru_sentiment_score는 50.0 중립으로 고정하세요. "
                    "단, MARKET/MINDSET/RISK/PSYCHOLOGY도 구루의 투자 행동 원칙으로는 적극 활용하세요."
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
                        "freshness_level": "N/A",
                        "latest_date": "N/A",
                        "latest_days_old": None,
                        "selected_docs": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            # Plan A: 종목 직접 검색
            specific_docs = self._search(company_name, search_type="SPECIFIC", k=30)

            specific_docs = self._dedupe_docs(specific_docs)

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

            # Plan B: 시장/마인드셋/리스크 관리 fallback 검색
            fallback_docs = self._build_fallback_docs()
            fallback_content_type = self._infer_fallback_content_type(fallback_docs)

            return self._format_result(
                company_name=company_name,
                specific_docs=specific_docs,
                fallback_docs=fallback_docs,
                content_type=fallback_content_type,
                is_specific_useful=False,
            )

        except Exception as e:
            return json.dumps(
                {
                    "is_data_valid": False,
                    "error": str(e),
                    "content_type_hint": "N/A",
                    "freshness_level": "N/A",
                    "latest_date": "N/A",
                    "latest_days_old": None,
                    "selected_docs": [],
                },
                ensure_ascii=False,
                indent=2,
            )


def get_guru_youtube_tool():
    return LocalYoutubeSearchTool()
