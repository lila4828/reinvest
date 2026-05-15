import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from services.guru_opinion_service import attach_guru_opinion


CONTENT_TYPES = {"SPECIFIC", "MARKET", "MINDSET", "RISK", "PSYCHOLOGY", "GENERAL", "N/A"}

POSITIVE_YOUTUBE_KEYWORDS = [
    "매수",
    "좋은 기업",
    "기회",
    "성장",
    "상승",
    "저평가",
    "모아갈",
    "기다릴",
    "buy",
    "growth",
    "opportunity",
]

NEGATIVE_YOUTUBE_KEYWORDS = [
    "매도",
    "위험",
    "리스크",
    "하락",
    "고평가",
    "주의",
    "손절",
    "비중 축소",
    "sell",
    "risk",
    "overvalued",
]


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
    """Transcript text 기반으로 문서 성격을 보조 분류한다."""
    if not text:
        return "GENERAL"

    normalized = text.replace(" ", "").lower()

    risk_keywords = [
        "리스크",
        "손절",
        "비중",
        "현금",
        "분할",
        "분할매수",
        "추격매수",
        "방어",
        "대응",
        "비중조절",
        "risk",
    ]
    mindset_keywords = [
        "마인드",
        "심리",
        "멘탈",
        "공포",
        "조급",
        "기다림",
        "인내",
        "확신",
        "감정",
        "원칙",
        "mindset",
        "psychology",
    ]
    market_keywords = [
        "시황",
        "시장",
        "나스닥",
        "금리",
        "환율",
        "수급",
        "미국",
        "코스피",
        "코스닥",
        "반도체",
        "2차전지",
        "macro",
        "market",
    ]
    psychology_keywords = [
        "수급",
        "차트",
        "심리",
        "가격 확인",
        "뉴스보다",
        "기술적",
    ]

    if any(keyword in normalized for keyword in risk_keywords):
        return "RISK"
    if any(keyword in normalized for keyword in mindset_keywords):
        return "MINDSET"
    if any(keyword in normalized for keyword in psychology_keywords):
        return "PSYCHOLOGY"
    if any(keyword in normalized for keyword in market_keywords):
        return "MARKET"

    return "GENERAL"


def _normalize_doc(doc, query: str, search_type: str):
    metadata = doc.metadata or {}

    date_text = metadata.get("date", "날짜 없음")
    days_old = _days_old(date_text)
    title = metadata.get("title", "제목 없음")
    source = metadata.get("source", "출처 없음")
    content = doc.page_content or ""
    theme_hint = _detect_content_theme(f"{title} {content}")

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


def _trim_text(text: str, limit: int = 220):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit]


def _extract_relevant_phrases(selected_docs: List[Dict[str, Any]], keywords: List[str], limit: int = 2):
    phrases = []
    for doc in selected_docs:
        content = _trim_text(doc.get("content"), 260)
        normalized = content.lower()
        if any(keyword.lower() in normalized for keyword in keywords):
            title = doc.get("title") or "제목 없음"
            date = doc.get("date") or "날짜 없음"
            phrases.append(f"{date} '{title}'에서 {content}")
        if len(phrases) >= limit:
            break
    return phrases


def build_youtube_fallback(
    error: str | None = None,
    company: str = "",
    ticker: str | None = None,
):
    data = {
        "guru_sentiment_score": 50.0,
        "key_strategy": "유의미한 유튜브 인사이트가 없어 중립으로 반영합니다.",
        "content_type": "N/A",
        "insight_date": "N/A",
        "freshness_level": "N/A",
        "mindset_summary": "직접적인 투자 심리 또는 마인드셋 관련 발언이 확인되지 않았습니다.",
        "market_principle": "직접적인 시장 대응 원칙이 확인되지 않았습니다.",
        "risk_control": "직접적인 리스크 관리 발언이 확인되지 않았습니다.",
        "guru_insight_details": "유효한 유튜브 인사이트를 찾지 못해 중립 fallback으로 처리했습니다.",
        "is_data_valid": False,
    }

    if error:
        data["error"] = error

    return attach_guru_opinion(company, ticker, data)


def parse_youtube_search_result(raw_result):
    if isinstance(raw_result, str):
        return json.loads(raw_result)

    if isinstance(raw_result, dict):
        return raw_result

    return {
        "is_data_valid": False,
        "error": f"unexpected youtube search result type: {type(raw_result).__name__}",
        "selected_docs": [],
        "content_type_hint": "N/A",
        "freshness_level": "N/A",
        "latest_date": "N/A",
    }


def normalize_content_type(content_type: str):
    content_type = str(content_type or "N/A").upper()
    if content_type in CONTENT_TYPES:
        return content_type
    return "GENERAL"


def score_youtube_docs(content_type: str, freshness_level: str, selected_docs):
    content_type = normalize_content_type(content_type)

    if content_type != "SPECIFIC" or freshness_level not in ["FRESH", "RECENT"]:
        return 50.0

    joined = " ".join(
        f"{doc.get('title', '')} {doc.get('content', '')}".lower()
        for doc in selected_docs
        if isinstance(doc, dict)
    )
    positive_hits = sum(1 for keyword in POSITIVE_YOUTUBE_KEYWORDS if keyword.lower() in joined)
    negative_hits = sum(1 for keyword in NEGATIVE_YOUTUBE_KEYWORDS if keyword.lower() in joined)

    score = 50.0 + min(20, positive_hits * 5) - min(20, negative_hits * 5)

    if freshness_level == "RECENT":
        score = 50.0 + ((score - 50.0) * 0.6)

    return float(max(35.0, min(65.0, score)))


def summarize_youtube_docs(selected_docs, max_docs=3):
    if not selected_docs:
        return "유효한 유튜브 인사이트가 없어 중립 fallback으로 처리했습니다."

    lines = []
    for doc in selected_docs[:max_docs]:
        date = doc.get("date") or "N/A"
        title = doc.get("title") or "제목 없음"
        search_type = doc.get("search_type") or doc.get("theme_hint") or "GENERAL"
        content = _trim_text(doc.get("content"), 260)
        lines.append(f"{date} / {title} / {search_type}: {content}")

    return "\n".join(lines)


def build_key_strategy(content_type: str, freshness_level: str, selected_docs):
    content_type = normalize_content_type(content_type)

    if content_type == "SPECIFIC":
        if freshness_level in ["FRESH", "RECENT"]:
            return "종목 직접 언급 자료를 참고하되, 스크립트에 없는 목표가·매수가·확신은 만들지 않습니다."
        return "종목 직접 언급은 있으나 최신성이 낮아 참고 강도를 낮추고 가격 판단은 시스템 계산값을 우선합니다."
    if content_type == "MARKET":
        return "시장 환경과 수급 원칙을 현재 종목의 진입 부담과 리스크 관리 관점에서만 참고합니다."
    if content_type == "MINDSET":
        return "추격매수보다 기다림, 분할 접근, 감정 통제를 우선하는 투자 태도로 해석합니다."
    if content_type == "RISK":
        return "현금 비중, 분할매수, 손실 제한 등 방어적 리스크 관리 원칙으로만 반영합니다."
    if content_type == "PSYCHOLOGY":
        return "뉴스보다 실제 가격과 수급 확인을 중시하는 심리·행동 원칙으로 반영합니다."

    return "직접적인 구루 인사이트가 제한적이므로 중립으로 반영합니다."


def build_mindset_summary(selected_docs):
    phrases = _extract_relevant_phrases(
        selected_docs,
        ["마인드", "심리", "멘탈", "공포", "조급", "기다림", "인내", "원칙", "mindset", "psychology"],
    )
    if phrases:
        return " / ".join(phrases)
    return "직접적인 투자 마인드셋 발언은 제한적입니다."


def build_market_principle(selected_docs):
    phrases = _extract_relevant_phrases(
        selected_docs,
        ["시황", "시장", "금리", "환율", "수급", "나스닥", "코스피", "코스닥", "market", "macro"],
    )
    if phrases:
        return " / ".join(phrases)
    return "직접적인 시장 대응 원칙은 제한적입니다."


def build_risk_control(selected_docs):
    phrases = _extract_relevant_phrases(
        selected_docs,
        ["리스크", "손절", "비중", "현금", "분할", "추격매수", "방어", "대응", "risk"],
    )
    if phrases:
        return " / ".join(phrases)
    return "직접적인 리스크 관리 발언은 제한적입니다."


def build_guru_insight_details(content_type: str, selected_docs):
    if not selected_docs:
        return "유의미한 유튜브 인사이트가 확인되지 않았습니다."

    content_type = normalize_content_type(content_type)
    prefix = {
        "SPECIFIC": "종목 직접 언급 기반 인사이트입니다.",
        "MARKET": "개별 종목 추천이 아니라 시장 원칙 기반 인사이트입니다.",
        "MINDSET": "개별 종목 추천이 아니라 투자 마인드셋 기반 인사이트입니다.",
        "RISK": "개별 종목 추천이 아니라 리스크 관리 원칙 기반 인사이트입니다.",
        "PSYCHOLOGY": "개별 종목 추천이 아니라 투자 심리 원칙 기반 인사이트입니다.",
        "GENERAL": "일반 투자 원칙 기반 인사이트입니다.",
        "N/A": "직접 인사이트가 제한적입니다.",
    }.get(content_type, "일반 투자 원칙 기반 인사이트입니다.")

    lines = [prefix]
    for doc in selected_docs[:4]:
        date = doc.get("date") or "날짜 없음"
        title = doc.get("title") or "제목 없음"
        theme = doc.get("theme_hint") or doc.get("search_type") or "GENERAL"
        content = _trim_text(doc.get("content"), 240)
        lines.append(f"- {date} '{title}'({theme}) 근거: {content}")

    if content_type != "SPECIFIC":
        lines.append("따라서 이 내용은 해당 종목의 직접 매수·매도 추천이 아니라 투자 태도와 리스크 관리 참고 자료로만 사용합니다.")

    return "\n".join(lines)[:1200]


def build_youtube_data_from_search(company: str, search_result):
    selected_docs = search_result.get("selected_docs") or []
    content_type = normalize_content_type(search_result.get("content_type_hint") or "N/A")
    freshness_level = search_result.get("freshness_level") or "N/A"
    insight_date = search_result.get("latest_date") or "N/A"

    if not search_result.get("is_data_valid") or not selected_docs:
        return build_youtube_fallback(
            search_result.get("error") or "no relevant youtube results",
            company=company,
        )

    guru_score = score_youtube_docs(content_type, freshness_level, selected_docs)

    payload = {
        "guru_sentiment_score": guru_score,
        "key_strategy": build_key_strategy(content_type, freshness_level, selected_docs),
        "content_type": content_type,
        "insight_date": insight_date,
        "freshness_level": freshness_level,
        "mindset_summary": build_mindset_summary(selected_docs),
        "market_principle": build_market_principle(selected_docs),
        "risk_control": build_risk_control(selected_docs),
        "guru_insight_details": build_guru_insight_details(content_type, selected_docs),
        "is_data_valid": True,
        "selected_docs": selected_docs[:8],
        "source_policy": (
            "selected_docs에 있는 제목, 날짜, transcript 내용만 사용했습니다. "
            "content_type이 SPECIFIC이 아니면 종목 직접 추천으로 해석하지 않습니다."
        ),
    }
    return attach_guru_opinion(company, None, payload)


class LocalYoutubeSearchTool:
    name: str = "local_youtube_search_tool"
    description: str = (
        "주알홍쌤 유튜브 로컬 Chroma DB를 읽기 전용으로 검색하는 도구입니다. "
        "종목명 또는 시장·투자 마인드셋 키워드를 입력하면 관련 transcript를 반환합니다. "
        "종목 직접 검색 결과가 약하면 시장 원칙, 투자 마인드셋, 수급·심리, 리스크 관리 중심의 Plan B 검색을 수행합니다."
    )

    db_path: str = "./chroma_db"

    def __init__(self):
        self._vector_db: Any = None

    def _get_vector_db(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY 누락: OpenAIEmbeddings를 사용할 수 없습니다.")

        if not os.path.exists(self.db_path):
            raise RuntimeError(
                f"유튜브 Chroma DB 경로가 없습니다: {self.db_path}. "
                "먼저 수동 유튜브 DB 업데이트 파이프라인을 실행해야 합니다."
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
        """종목 직접 자료가 약하면 투자 철학·시장 대응·리스크 관리 자료를 함께 검색한다."""
        fallback_queries = [
            {"query": "시황 금리 환율 투자 전략", "search_type": "MARKET"},
            {"query": "시장 심리 투자 마인드 전략", "search_type": "MINDSET"},
            {"query": "주식시장 대응 현금 비중 리스크 관리", "search_type": "RISK"},
            {"query": "추격매수 분할매수 관망 리스크 관리", "search_type": "RISK"},
            {"query": "수급 심리 차트 뉴스보다 가격 확인", "search_type": "PSYCHOLOGY"},
            {"query": "좋은 기업 좋은 매수 가격 투자 원칙", "search_type": "MINDSET"},
            {"query": "패닉 매매 공포 탐욕 투자 원칙", "search_type": "MINDSET"},
            {"query": "기다림 인내 분할매수 투자 마인드", "search_type": "MINDSET"},
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
        latest_date = latest_doc.get("date", "날짜 없음")
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
        """Plan B 결과 중 어떤 성격이 강한지 판단한다."""
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
            if type_counts["RISK"] >= type_counts["MINDSET"] and type_counts["RISK"] >= type_counts["PSYCHOLOGY"]:
                return "RISK"
            if type_counts["PSYCHOLOGY"] >= type_counts["MINDSET"]:
                return "PSYCHOLOGY"
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
            "content_type_hint": normalize_content_type(content_type),
            "is_specific_useful": is_specific_useful,
            "specific_result_count": len(specific_docs),
            "fallback_result_count": len(fallback_docs),
            "freshness_level": freshness["freshness_level"],
            "latest_date": freshness["latest_date"],
            "latest_days_old": freshness["latest_days_old"],
            "selected_docs": selected_docs,
            "interpretation_guide": {
                "SPECIFIC": "종목 직접 언급 자료입니다. transcript에 없는 목표가·매수가·확신은 만들지 않습니다.",
                "MARKET": "시장 환경 자료입니다. 개별 종목 추천이 아니라 시장 대응 원칙으로만 해석합니다.",
                "MINDSET": "투자 마인드셋 자료입니다. 매수·매도 추천이 아니라 행동 원칙으로 해석합니다.",
                "RISK": "리스크 관리 자료입니다. 가격 예측이 아니라 방어 원칙으로 해석합니다.",
                "PSYCHOLOGY": "수급·심리 자료입니다. 실제 가격 확인과 심리 통제 원칙으로 해석합니다.",
                "GENERAL": "일반 투자 원칙 자료입니다.",
                "N/A": "유의미한 구루 인사이트가 없습니다.",
            },
            "scoring_hint": {
                "rule": (
                    "content_type_hint가 SPECIFIC이고 최신 종목 직접 분석일 때만 guru_sentiment_score를 방향성 있게 부여합니다. "
                    "MARKET, MINDSET, RISK, PSYCHOLOGY, GENERAL은 50.0 중립으로 유지합니다."
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

            specific_docs = self._search(company_name, search_type="SPECIFIC", k=30)
            specific_docs = self._dedupe_docs(specific_docs)

            is_specific_useful = self._is_specific_result_useful(
                specific_docs,
                company_name,
            )

            if is_specific_useful:
                return self._format_result(
                    company_name=company_name,
                    specific_docs=specific_docs,
                    fallback_docs=[],
                    content_type="SPECIFIC",
                    is_specific_useful=True,
                )

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


def run_local_youtube_search(company: str):
    try:
        return parse_youtube_search_result(get_guru_youtube_tool()._run(company))
    except Exception as e:
        return {
            "is_data_valid": False,
            "error": str(e),
            "selected_docs": [],
            "content_type_hint": "N/A",
            "freshness_level": "N/A",
            "latest_date": "N/A",
        }
