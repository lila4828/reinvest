import os
import json
import ast
import requests

from services.news_brief_service import attach_news_brief


class SafeSerperNewsTool:
    name: str = "safe_serper_news_search"
    description: str = (
        "Google News 기반 금융 뉴스 검색 도구입니다. "
        "기업명과 검색어를 입력하면 실제 검색 결과를 JSON으로 반환합니다."
    )

    def _normalize_results(self, raw_result):
        """
        Serper 검색 결과를 LLM이 읽기 쉬운 구조화된 results 배열로 변환합니다.
        결과 형태가 dict/list/string 등으로 달라도 최대한 안전하게 처리합니다.
        """
        try:
            # raw_result가 문자열이면 dict/list로 파싱 시도
            if isinstance(raw_result, str):
                parsed = None

                # 1차 JSON 파싱
                try:
                    parsed = json.loads(raw_result)
                except Exception:
                    pass

                # 2차 Python literal 파싱
                if parsed is None:
                    try:
                        parsed = ast.literal_eval(raw_result)
                    except Exception:
                        parsed = None

                # 파싱 실패 시 원문 일부만 반환
                if parsed is None:
                    return [
                        {
                            "title": "검색 결과 원문",
                            "source": "Serper",
                            "date": "N/A",
                            "link": "N/A",
                            "snippet": raw_result[:1200],
                        }
                    ]

                raw_result = parsed

            # Serper 결과가 dict인 경우
            if isinstance(raw_result, dict):
                candidates = []

                # news 우선 결과
                if isinstance(raw_result.get("news"), list):
                    candidates.extend(raw_result.get("news"))

                # organic 검색 결과 fallback
                if isinstance(raw_result.get("organic"), list):
                    candidates.extend(raw_result.get("organic"))

                # results 키 fallback
                if isinstance(raw_result.get("results"), list):
                    candidates.extend(raw_result.get("results"))

            # Serper 결과가 list인 경우
            elif isinstance(raw_result, list):
                candidates = raw_result

            else:
                candidates = []

            normalized = []

            for item in candidates[:10]:
                if not isinstance(item, dict):
                    continue

                title = (
                    item.get("title")
                    or item.get("name")
                    or "제목 없음"
                )

                source = (
                    item.get("source")
                    or item.get("publisher")
                    or item.get("site")
                    or "출처 불명"
                )

                date = (
                    item.get("date")
                    or item.get("publishedDate")
                    or item.get("published")
                    or "날짜 없음"
                )

                link = (
                    item.get("link")
                    or item.get("url")
                    or "URL 없음"
                )

                snippet = (
                    item.get("snippet")
                    or item.get("description")
                    or item.get("summary")
                    or item.get("content")
                    or ""
                )

                # 제목과 요약이 모두 비어 있으면 제외
                if title == "제목 없음" and not snippet:
                    continue

                normalized.append(
                    {
                        "title": str(title)[:300],
                        "source": str(source)[:100],
                        "date": str(date)[:100],
                        "link": str(link)[:500],
                        "snippet": str(snippet)[:1000],
                    }
                )

            return normalized

        except Exception as e:
            return [
                {
                    "title": "검색 결과 파싱 실패",
                    "source": "Serper",
                    "date": "N/A",
                    "link": "N/A",
                    "snippet": str(e),
                }
            ]

    def _run(self, query: str) -> str:
        try:
            if not os.getenv("SERPER_API_KEY"):
                return json.dumps(
                    {
                        "is_data_valid": False,
                        "error": "SERPER_API_KEY 누락",
                        "query": query,
                        "results": [],
                    },
                    ensure_ascii=False,
                )

            # Serper 호출 직전에만 news 요청 지정
            response = requests.post(
                "https://google.serper.dev/news",
                headers={
                    "X-API-KEY": os.getenv("SERPER_API_KEY"),
                    "Content-Type": "application/json",
                },
                json={"q": query},
                timeout=20,
            )
            response.raise_for_status()
            raw_result = response.json()

            if not raw_result:
                return json.dumps(
                    {
                        "is_data_valid": False,
                        "error": "검색 결과 없음",
                        "query": query,
                        "results": [],
                    },
                    ensure_ascii=False,
                )

            parsed_results = self._normalize_results(raw_result)

            if not parsed_results:
                return json.dumps(
                    {
                        "is_data_valid": False,
                        "error": "유효한 뉴스 결과 없음",
                        "query": query,
                        "results": [],
                    },
                    ensure_ascii=False,
                )

            return json.dumps(
                {
                    "is_data_valid": True,
                    "error": None,
                    "query": query,
                    "result_count": len(parsed_results),
                    "results": parsed_results,
                },
                ensure_ascii=False,
            )

        except Exception as e:
            return json.dumps(
                {
                    "is_data_valid": False,
                    "error": str(e),
                    "query": query,
                    "results": [],
                },
                ensure_ascii=False,
            )


search_tool = SafeSerperNewsTool()


POSITIVE_KEYWORDS = [
    "상승",
    "호재",
    "수주",
    "계약",
    "실적 개선",
    "목표가 상향",
    "흑자",
    "성장",
    "증가",
    "호실적",
    "어닝 서프라이즈",
    "신제품",
    "투자 확대",
    "earnings beat",
    "upgrade",
    "outperform",
    "buy",
    "record",
    "growth",
]

NEGATIVE_KEYWORDS = [
    "하락",
    "악재",
    "실적 부진",
    "목표가 하향",
    "적자",
    "소송",
    "감소",
    "부진",
    "리콜",
    "규제",
    "감산",
    "우려",
    "downgrade",
    "sell",
    "miss",
    "loss",
    "recall",
    "risk",
]


def build_research_fallback(error: str | None = None):
    data = {
        "sentiment_score": 50,
        "momentum_strength": "LOW",
        "news_summary": "유효한 최신 뉴스 결과가 부족해 중립으로 처리했습니다.",
        "sentiment_reason": "검색 실패 또는 유효한 뉴스 부족으로 긍정/부정 방향성을 판단하지 않았습니다.",
        "issue_breakdown": {
            "positive": [],
            "negative": [],
            "neutral": [],
        },
        "is_data_valid": False,
        "results": [],
    }

    if error:
        data["error"] = error

    return attach_news_brief(data)


def build_research_queries(company: str):
    return [
        f"{company} 최신 뉴스 주가 전망",
        f"{company} 주가 수급 투자심리 기관 외국인",
        f"{company} 실적 전망 목표가 증권사 리포트",
        f"{company} 산업 경쟁사 시장점유율 수요 전망",
        f"{company} stock news earnings analyst rating outlook",
    ]


def parse_research_search_result(raw_result, query: str):
    if isinstance(raw_result, str):
        return json.loads(raw_result)

    if isinstance(raw_result, dict):
        return raw_result

    return {
        "is_data_valid": False,
        "error": f"unexpected research search result type: {type(raw_result).__name__}",
        "query": query,
        "results": [],
    }


def run_research_search(query: str):
    return parse_research_search_result(search_tool._run(query), query)


def _is_low_quality_result(title: str, snippet: str, source: str):
    text = f"{title} {snippet} {source}".lower()
    low_quality_markers = [
        "광고",
        "블로그",
        "카페",
        "지식인",
        "sponsored",
        "advertisement",
    ]
    return any(marker in text for marker in low_quality_markers)


def dedupe_research_results(results):
    deduped = []
    seen = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        link = str(item.get("link") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        source = str(item.get("source") or "출처 불명").strip()

        if not title and not snippet:
            continue

        if _is_low_quality_result(title, snippet, source):
            continue

        key = (link or title).lower()
        if key in seen:
            continue

        seen.add(key)
        deduped.append(
            {
                "title": title[:300] or "제목 없음",
                "source": source[:100] or "출처 불명",
                "date": str(item.get("date") or "날짜 없음")[:100],
                "link": link[:500] or "URL 없음",
                "snippet": snippet[:1000],
            }
        )

    return deduped


def classify_research_result(item):
    title = str(item.get("title") or "")
    snippet = str(item.get("snippet") or "")
    text = f"{title} {snippet}".lower()

    positive_hits = [
        keyword for keyword in POSITIVE_KEYWORDS
        if keyword.lower() in text
    ]
    negative_hits = [
        keyword for keyword in NEGATIVE_KEYWORDS
        if keyword.lower() in text
    ]

    if len(positive_hits) > len(negative_hits):
        label = "positive"
        reason = f"긍정 키워드: {', '.join(positive_hits[:3])}"
    elif len(negative_hits) > len(positive_hits):
        label = "negative"
        reason = f"부정 키워드: {', '.join(negative_hits[:3])}"
    else:
        label = "neutral"
        reason = "뚜렷한 긍정/부정 키워드가 제한적"

    return {
        "label": label,
        "reason": reason,
        "title": item.get("title") or "제목 없음",
        "source": item.get("source") or "출처 불명",
        "date": item.get("date") or "날짜 없음",
        "link": item.get("link") or "URL 없음",
        "snippet": item.get("snippet") or "",
    }


def classify_research_results(results):
    breakdown = {
        "positive": [],
        "negative": [],
        "neutral": [],
    }

    for item in results:
        classified = classify_research_result(item)
        breakdown[classified["label"]].append(classified)

    return breakdown


def score_research_results(results):
    breakdown = classify_research_results(results)
    positive_count = len(breakdown["positive"])
    negative_count = len(breakdown["negative"])
    neutral_count = len(breakdown["neutral"])

    score = 50 + min(25, positive_count * 7) - min(25, negative_count * 7)
    score = max(15, min(85, score))

    distance = abs(score - 50)
    if len(results) >= 3 and distance >= 15:
        strength = "HIGH"
    elif distance >= 8:
        strength = "MEDIUM"
    else:
        strength = "LOW"

    reason = (
        f"긍정 {positive_count}건, 부정 {negative_count}건, 중립 {neutral_count}건으로 "
        f"뉴스 모멘텀 강도는 {strength}, 점수는 {score}점입니다. "
        "뉴스의 숫자나 전망은 참고 신호이며 감사된 재무제표 사실로 취급하지 않습니다."
    )

    return score, strength, breakdown, reason


def _format_issue_line(item):
    title = item.get("title") or "제목 없음"
    source = item.get("source") or "출처 불명"
    date = item.get("date") or "날짜 없음"
    snippet = str(item.get("snippet") or "")
    reason = item.get("reason") or ""
    return f"{title} ({source}, {date}) - {reason}. {snippet[:180]}"


def summarize_research_results(company: str, results, breakdown=None, sentiment_reason: str = ""):
    if not results:
        return "유효한 최신 뉴스 결과가 없어 중립 fallback으로 처리했습니다."

    breakdown = breakdown or classify_research_results(results)
    lines = [f"{company} 뉴스 종합: {sentiment_reason}"]

    for label, label_text in [
        ("positive", "긍정 이슈"),
        ("negative", "부정 이슈"),
        ("neutral", "중립/관찰 이슈"),
    ]:
        selected = breakdown.get(label, [])[:2]
        if not selected:
            continue
        lines.append(f"{label_text}:")
        for item in selected:
            lines.append(f"- {_format_issue_line(item)}")

    return "\n".join(lines[:8])


def collect_research_data(company: str):
    all_results = []
    errors = []
    queries = build_research_queries(company)

    for query in queries:
        try:
            search_result = run_research_search(query)
        except Exception as e:
            errors.append(f"{query}: {e}")
            continue

        if not search_result.get("is_data_valid"):
            error = search_result.get("error")
            if error:
                errors.append(f"{query}: {error}")
            continue

        all_results.extend(search_result.get("results") or [])

    results = dedupe_research_results(all_results)

    if not results:
        fallback = build_research_fallback(
            "; ".join(errors) if errors else "no valid news results"
        )
        fallback["queries"] = queries
        return fallback

    sentiment_score, momentum_strength, breakdown, sentiment_reason = score_research_results(results)
    news_summary = summarize_research_results(
        company,
        results,
        breakdown=breakdown,
        sentiment_reason=sentiment_reason,
    )

    payload = {
        "sentiment_score": sentiment_score,
        "momentum_strength": momentum_strength,
        "news_summary": news_summary,
        "sentiment_reason": sentiment_reason,
        "issue_breakdown": {
            key: value[:5]
            for key, value in breakdown.items()
        },
        "is_data_valid": True,
        "queries": queries,
        "result_count": len(results),
        "results": results[:10],
        "errors": errors,
    }
    return attach_news_brief(payload)
