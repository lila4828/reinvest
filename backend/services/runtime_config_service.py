import os


DEFAULT_OPENAI_ANALYSIS_MODEL = "gpt-5.5"
DEFAULT_OPENAI_NEWS_BRIEF_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_GURU_OPINION_MODEL = "gpt-5.4"
DEFAULT_OPENAI_GURU_STRATEGY_MODEL = "gpt-5.4"


def require_env(name: str):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


def get_openai_analysis_model():
    return os.getenv("OPENAI_ANALYSIS_MODEL", DEFAULT_OPENAI_ANALYSIS_MODEL)


def get_openai_news_brief_model():
    return os.getenv("OPENAI_NEWS_BRIEF_MODEL", DEFAULT_OPENAI_NEWS_BRIEF_MODEL)


def get_openai_guru_opinion_model():
    return os.getenv("OPENAI_GURU_OPINION_MODEL", DEFAULT_OPENAI_GURU_OPINION_MODEL)


def get_openai_guru_strategy_model():
    return os.getenv("OPENAI_GURU_STRATEGY_MODEL", DEFAULT_OPENAI_GURU_STRATEGY_MODEL)
