import os
import json
from crewai.tools import BaseTool
from crewai_tools import SerperDevTool


class SafeSerperNewsTool(BaseTool):
    name: str = "safe_serper_news_search"
    description: str = (
        "Google News 기반 금융 뉴스 검색 도구입니다. "
        "기업명과 검색 앵글을 입력하면 실제 검색 결과를 JSON으로 반환합니다."
    )

    def _run(self, query: str) -> str:
        try:
            if not os.getenv("SERPER_API_KEY"):
                return json.dumps(
                    {
                        "is_data_valid": False,
                        "error": "SERPER_API_KEY 누락",
                        "results": [],
                    },
                    ensure_ascii=False,
                )

            # SerperDevTool 호출 직전에만 news 타입 지정
            old_search_type = os.environ.get("SERPER_SEARCH_TYPE")
            os.environ["SERPER_SEARCH_TYPE"] = "news"

            try:
                search_tool = SerperDevTool()
                raw_result = search_tool.run(query)
            finally:
                # 다른 Serper 도구에 전역 영향 주지 않도록 복구
                if old_search_type is None:
                    os.environ.pop("SERPER_SEARCH_TYPE", None)
                else:
                    os.environ["SERPER_SEARCH_TYPE"] = old_search_type

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

            return json.dumps(
                {
                    "is_data_valid": True,
                    "error": None,
                    "query": query,
                    "raw_result": str(raw_result)[:5000],
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