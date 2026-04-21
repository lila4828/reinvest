import os
from crewai_tools import SerperDevTool

# Serper가 전체 웹 문서가 아닌 '구글 뉴스' 탭에서만 검색하도록 강제
os.environ["SERPER_SEARCH_TYPE"] = "news" 

search_tool = SerperDevTool()