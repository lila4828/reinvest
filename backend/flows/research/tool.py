import os
import json
import ast
import requests


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
