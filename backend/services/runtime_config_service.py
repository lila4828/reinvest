import os


DEFAULT_OPENAI_ANALYSIS_MODEL = "gpt-5.5"
DEFAULT_OPENAI_NEWS_BRIEF_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_GURU_OPINION_MODEL = "gpt-5.4"
DEFAULT_OPENAI_GURU_STRATEGY_MODEL = "gpt-5.4"

TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
FALSE_ENV_VALUES = {"0", "false", "no", "off"}


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


def _get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in TRUE_ENV_VALUES:
        return True
    if normalized in FALSE_ENV_VALUES:
        return False
    return default


def is_news_brief_llm_enabled():
    return _get_env_bool("REPORT_NEWS_BRIEF_LLM_ENABLED", default=True)


def is_guru_opinion_llm_enabled():
    return _get_env_bool("REPORT_GURU_OPINION_LLM_ENABLED", default=True)


def is_guru_strategy_llm_enabled():
    return _get_env_bool("REPORT_GURU_STRATEGY_LLM_ENABLED", default=True)


def is_guru_strategy_recent_rag_enabled():
    return _get_env_bool("REPORT_GURU_STRATEGY_RAG_ENABLED", default=True)


def _get_env_int(name: str, default: int, minimum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default

    if minimum is not None:
        return max(minimum, value)
    return value


def get_guru_strategy_rag_lookback_days():
    return _get_env_int("REPORT_GURU_STRATEGY_RAG_LOOKBACK_DAYS", 3, minimum=1)


def get_guru_strategy_rag_max_videos():
    return _get_env_int("REPORT_GURU_STRATEGY_RAG_MAX_VIDEOS", 3, minimum=1)


def get_guru_strategy_rag_max_docs():
    return _get_env_int("REPORT_GURU_STRATEGY_RAG_MAX_DOCS", 6, minimum=1)
