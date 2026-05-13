import os
import json
import ast
import requests


class SafeSerperNewsTool:
    name: str = "safe_serper_news_search"
    description: str = (
        "Google News 湲곕컲 湲덉쑖 ?댁뒪 寃???꾧뎄?낅땲?? "
        "湲곗뾽紐낃낵 寃???듦????낅젰?섎㈃ ?ㅼ젣 寃??寃곌낵瑜?JSON?쇰줈 諛섑솚?⑸땲??"
    )

    def _normalize_results(self, raw_result):
        """
        SerperDevTool 寃곌낵瑜?LLM???쎄린 ?ъ슫 援ъ“?붾맂 results 諛곗뿴濡?蹂?섑빀?덈떎.
        寃곌낵 ?뺥깭媛 dict/list/string ?깆쑝濡??щ씪?몃룄 理쒕????덉쟾?섍쾶 泥섎━?⑸땲??
        """
        try:
            # raw_result媛 臾몄옄?댁씠硫?dict/list濡??뚯떛 ?쒕룄
            if isinstance(raw_result, str):
                parsed = None

                # 1李? JSON ?뚯떛
                try:
                    parsed = json.loads(raw_result)
                except Exception:
                    pass

                # 2李? Python literal ?뚯떛
                if parsed is None:
                    try:
                        parsed = ast.literal_eval(raw_result)
                    except Exception:
                        parsed = None

                # ?뚯떛 ?ㅽ뙣 ???먮Ц ?쇰?留?諛섑솚
                if parsed is None:
                    return [
                        {
                            "title": "寃??寃곌낵 ?먮Ц",
                            "source": "Serper",
                            "date": "N/A",
                            "link": "N/A",
                            "snippet": raw_result[:1200],
                        }
                    ]

                raw_result = parsed

            # Serper 寃곌낵媛 dict??寃쎌슦
            if isinstance(raw_result, dict):
                candidates = []

                # news ???寃곌낵
                if isinstance(raw_result.get("news"), list):
                    candidates.extend(raw_result.get("news"))

                # organic ???寃곌낵 fallback
                if isinstance(raw_result.get("organic"), list):
                    candidates.extend(raw_result.get("organic"))

                # results ??fallback
                if isinstance(raw_result.get("results"), list):
                    candidates.extend(raw_result.get("results"))

            # Serper 寃곌낵媛 list??寃쎌슦
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
                    or "?쒕ぉ ?놁쓬"
                )

                source = (
                    item.get("source")
                    or item.get("publisher")
                    or item.get("site")
                    or "異쒖쿂 遺덈챸"
                )

                date = (
                    item.get("date")
                    or item.get("publishedDate")
                    or item.get("published")
                    or "?좎쭨 ?놁쓬"
                )

                link = (
                    item.get("link")
                    or item.get("url")
                    or "URL ?놁쓬"
                )

                snippet = (
                    item.get("snippet")
                    or item.get("description")
                    or item.get("summary")
                    or item.get("content")
                    or ""
                )

                # ?쒕ぉ怨??붿빟??????鍮꾩뼱 ?덉쑝硫??쒖쇅
                if title == "?쒕ぉ ?놁쓬" and not snippet:
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
                    "title": "寃??寃곌낵 ?뚯떛 ?ㅽ뙣",
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
                        "error": "SERPER_API_KEY ?꾨씫",
                        "query": query,
                        "results": [],
                    },
                    ensure_ascii=False,
                )

            # SerperDevTool ?몄텧 吏곸쟾?먮쭔 news ???吏??
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
                        "error": "寃??寃곌낵 ?놁쓬",
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
                        "error": "?좏슚???댁뒪 寃곌낵 ?놁쓬",
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
