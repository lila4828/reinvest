import os


DEFAULT_OPENAI_ANALYSIS_MODEL = "gpt-5.5"
DEFAULT_OPENAI_NEWS_BRIEF_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_GURU_OPINION_MODEL = "gpt-5.4"
DEFAULT_OPENAI_GURU_STRATEGY_MODEL = "gpt-5.4"

TRUE_ENV_VALUES = {"1", "true", "yes", "on"}


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


def is_news_brief_llm_enabled():
    return os.getenv("REPORT_NEWS_BRIEF_LLM_ENABLED", "").strip().lower() in TRUE_ENV_VALUES


def is_guru_opinion_llm_enabled():
    return os.getenv("REPORT_GURU_OPINION_LLM_ENABLED", "").strip().lower() in TRUE_ENV_VALUES
