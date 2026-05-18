import os
import uuid
import hmac
import json
import uvicorn
import traceback
import logging
from datetime import datetime, timedelta
from threading import Lock
from urllib.parse import unquote
from logging.handlers import RotatingFileHandler
import requests

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from stock_search.search_store import (
    get_stock_options,
    search_json_stocks,
    save_stock_to_cache,
    dedupe_stock_results,
)
from services.report_metadata_service import (
    find_existing_daily_reports,
    get_report_market_info,
)

load_dotenv()

# ---------------------------------------------------------
# API 전용 로깅
# ---------------------------------------------------------
api_log_file_handler = RotatingFileHandler(
    "api.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)

api_logger = logging.getLogger("ai_reinvest_api")
api_logger.setLevel(logging.INFO)
api_logger.propagate = False

if not api_logger.handlers:
    api_logger.addHandler(api_log_file_handler)
    api_logger.addHandler(logging.StreamHandler())

for handler in api_logger.handlers:
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )


app = FastAPI(title="AI-Reinvest API Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULT_DIR = "result"
RESULT_DIR_ABSPATH = os.path.abspath(RESULT_DIR)

SESSION_COOKIE_NAME = "ai_reinvest_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24  # 24시간

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SESSION_SECRET = os.getenv("SESSION_SECRET")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

sessions = {}
jobs = {}
jobs_lock = Lock()


def get_report_meta_filename(filename: str):
    if not filename or filename == "summary.md" or not filename.endswith(".md"):
        return None

    return filename[:-3] + ".meta.json"


def load_report_meta(date: str, filename: str):
    meta_filename = get_report_meta_filename(filename)

    if not meta_filename:
        return None

    meta_path = os.path.join(RESULT_DIR_ABSPATH, date, meta_filename)
    abs_meta_path = os.path.abspath(meta_path)

    if not abs_meta_path.startswith(RESULT_DIR_ABSPATH):
        api_logger.warning(
            f"invalid report meta path blocked: date={date}, filename={filename}"
        )
        return None

    if not os.path.exists(abs_meta_path):
        return None

    try:
        with open(abs_meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        api_logger.warning(
            f"report meta load failed: path={abs_meta_path}, error={e}"
        )
        return None


def build_report_list_meta_summary(date: str, filename: str):
    meta_filename = get_report_meta_filename(filename)
    fallback = {
        "status": None,
        "investment_opinion": None,
        "one_line_conclusion": None,
        "executive_summary": [],
        "current_price": None,
        "split_buy_price": None,
        "sell_review_price": None,
        "failed_reason": None,
        "meta_filename": meta_filename,
        "has_meta": False,
    }

    if not meta_filename:
        return fallback

    meta = load_report_meta(date, filename)

    if not isinstance(meta, dict):
        return fallback

    price = meta.get("price")

    if not isinstance(price, dict):
        price = {}

    return {
        "status": meta.get("status"),
        "investment_opinion": meta.get("investment_opinion"),
        "one_line_conclusion": meta.get("one_line_conclusion"),
        "executive_summary": (
            meta.get("executive_summary")
            if isinstance(meta.get("executive_summary"), list)
            else []
        ),
        "current_price": price.get("current_price"),
        "split_buy_price": price.get("split_buy_price"),
        "sell_review_price": price.get("sell_review_price"),
        "failed_reason": meta.get("failed_reason"),
        "meta_filename": meta_filename,
        "has_meta": True,
    }


class LoginRequest(BaseModel):
    username: str
    password: str


class StockInput(BaseModel):
    ticker: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    exchange: str | None = None
    quote_type: str | None = "EQUITY"

class RunReportRequest(BaseModel):
    stocks: list[StockInput]

def require_auth_env():
    missing = []

    if not ADMIN_USERNAME:
        missing.append("ADMIN_USERNAME")

    if not ADMIN_PASSWORD:
        missing.append("ADMIN_PASSWORD")

    if not SESSION_SECRET:
        missing.append("SESSION_SECRET")

    if missing:
        raise RuntimeError(f"환경변수 누락: {', '.join(missing)}")


def create_session_id():
    raw_token = uuid.uuid4().hex
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        raw_token.encode("utf-8"),
        "sha256",
    ).hexdigest()

    return f"{raw_token}.{signature}"


def is_valid_session_signature(session_id: str):
    if not session_id or "." not in session_id:
        return False

    raw_token, signature = session_id.split(".", 1)

    expected_signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        raw_token.encode("utf-8"),
        "sha256",
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def cleanup_expired_sessions():
    now = datetime.now()

    expired_session_ids = [
        session_id
        for session_id, session_data in sessions.items()
        if session_data["expires_at"] < now
    ]

    for session_id in expired_session_ids:
        sessions.pop(session_id, None)

    if expired_session_ids:
        api_logger.info(f"만료 세션 정리: count={len(expired_session_ids)}")


def get_current_session(request: Request):
    require_auth_env()
    cleanup_expired_sessions()

    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    if not is_valid_session_signature(session_id):
        api_logger.warning("유효하지 않은 세션 서명 요청 차단")
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다.")

    session_data = sessions.get(session_id)

    if not session_data:
        raise HTTPException(status_code=401, detail="세션이 만료되었거나 존재하지 않습니다.")

    return {
        "session_id": session_id,
        **session_data,
    }


def get_owned_job(job_id: str, session):
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        api_logger.warning(f"존재하지 않는 job 조회: job_id={job_id}")
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    if job["session_id"] != session["session_id"]:
        api_logger.warning(
            f"job 접근 권한 없음: job_id={job_id}, username={session['username']}"
        )
        raise HTTPException(status_code=403, detail="이 작업에 접근할 권한이 없습니다.")

    return job


def has_running_job(session_id: str):
    with jobs_lock:
        return any(
            job["session_id"] == session_id
            and job["status"] in ["pending", "running"]
            for job in jobs.values()
        )


def build_targets_status_from_stocks(
    stocks,
    status="pending",
    current_step="pending",
    errors=None,
    summary_saved=False,
):
    return [
        {
            "ticker": stock.get("ticker"),
            "company_name": stock.get("company") or stock.get("company_name"),
            "status": status,
            "current_step": current_step,
            "errors": errors or [],
            "summary_saved": summary_saved,
        }
        for stock in stocks
    ]


def build_targets_status_from_states(report_states):
    targets_status = []

    for state in report_states or []:
        targets_status.append(
            {
                "ticker": state.get("ticker"),
                "company_name": state.get("company_name") or state.get("company"),
                "status": state.get("status"),
                "current_step": state.get("current_step"),
                "errors": state.get("errors") or [],
                "summary_saved": bool(state.get("summary_saved")),
            }
        )

    return targets_status


INDIVIDUAL_REPORT_STEPS = {
    "accounting",
    "research",
    "youtube_rag",
    "price",
    "analysis",
    "report_save",
    "summary_save",
    "report_generated",
    "completed",
    "failed",
    "partial_failed",
}

TERMINAL_TARGET_STATUSES = {"completed", "success", "failed", "partial_failed"}


def update_job_target_status(job_id: str, state):
    state_status = build_targets_status_from_states([state])

    if not state_status:
        return

    next_item = state_status[0]

    with jobs_lock:
        job = jobs.get(job_id)

        if not job:
            return

        targets_status = job.get("targets_status") or build_targets_status_from_stocks(
            job.get("stocks", []),
        )
        updated = False

        for index, item in enumerate(targets_status):
            if item.get("ticker") == next_item.get("ticker"):
                targets_status[index] = {
                    **item,
                    **next_item,
                }
                updated = True
                break

        if not updated:
            targets_status.append(next_item)

        if next_item.get("current_step") in INDIVIDUAL_REPORT_STEPS:
            for item in targets_status:
                if item.get("ticker") == next_item.get("ticker"):
                    continue

                if item.get("status") in TERMINAL_TARGET_STATUSES:
                    continue

                if item.get("current_step") == "macro":
                    item["current_step"] = "pending"

        job["targets_status"] = targets_status


def normalize_ticker_for_analysis(ticker: str):
    ticker = str(ticker or "").strip().upper()

    if (
        len(ticker) == 10
        and ticker.startswith("A")
        and ticker[1:7].isalnum()
        and ticker[7:] in [".KS", ".KQ"]
    ):
        return ticker[1:]

    return ticker


def run_report_background(job_id: str, stock_pool: list[tuple[str, str]]):
    api_logger.info(f"리포트 작업 시작: job_id={job_id}, stocks={stock_pool}")

    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "running"
            jobs[job_id]["started_at"] = datetime.now().isoformat(timespec="seconds")
            jobs[job_id]["targets_status"] = build_targets_status_from_stocks(
                jobs[job_id].get("stocks", []),
                status="running",
                current_step="macro",
            )

    try:
        from pipelines.report_pipeline import run_report_pipeline, save_pipeline_output
        
        output = run_report_pipeline(
            stock_pool=stock_pool,
            status_callback=lambda state: update_job_target_status(job_id, state),
        )
        result_dir = save_pipeline_output(
            output,
            status_callback=lambda state: update_job_target_status(job_id, state),
        )

        report_count = len(output.get("reports", []))
        result_date = output["date"]
        targets_status = build_targets_status_from_states(
            output.get("_report_states", [])
        )

        with jobs_lock:
            jobs[job_id]["status"] = "success"
            jobs[job_id]["finished_at"] = datetime.now().isoformat(timespec="seconds")
            jobs[job_id]["result_date"] = result_date
            jobs[job_id]["result_dir"] = result_dir
            jobs[job_id]["report_count"] = report_count
            jobs[job_id]["error"] = None
            jobs[job_id]["targets_status"] = targets_status or build_targets_status_from_stocks(
                jobs[job_id].get("stocks", []),
                status="completed",
                current_step="completed",
                summary_saved=True,
            )

        api_logger.info(
            f"리포트 작업 성공: job_id={job_id}, "
            f"result_dir={result_dir}, report_count={report_count}"
        )

    except Exception as e:
        error_traceback = traceback.format_exc()

        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["finished_at"] = datetime.now().isoformat(timespec="seconds")
            jobs[job_id]["error"] = str(e)
            jobs[job_id]["traceback"] = error_traceback
            jobs[job_id]["targets_status"] = build_targets_status_from_stocks(
                jobs[job_id].get("stocks", []),
                status="failed",
                current_step="failed",
                errors=[str(e)],
            )

        api_logger.exception(f"리포트 작업 실패: job_id={job_id}, error={e}")


@app.post("/api/login")
def login(payload: LoginRequest, response: Response):
    require_auth_env()
    cleanup_expired_sessions()

    username = payload.username.strip()
    password = payload.password

    is_valid_username = hmac.compare_digest(username, ADMIN_USERNAME)
    is_valid_password = hmac.compare_digest(password, ADMIN_PASSWORD)

    if not is_valid_username or not is_valid_password:
        api_logger.warning(f"로그인 실패: username={username}")
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    session_id = create_session_id()
    expires_at = datetime.now() + timedelta(seconds=SESSION_MAX_AGE_SECONDS)

    sessions[session_id] = {
        "username": ADMIN_USERNAME,
        "created_at": datetime.now(),
        "expires_at": expires_at,
    }

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )

    api_logger.info(f"로그인 성공: username={ADMIN_USERNAME}")

    return {
        "ok": True,
        "username": ADMIN_USERNAME,
        "message": "로그인 성공",
    }


@app.post("/api/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        session_data = sessions.pop(session_id, None)
        username = session_data.get("username") if session_data else "unknown"
        api_logger.info(f"로그아웃 완료: username={username}")
    else:
        api_logger.info("로그아웃 요청: 세션 없음")

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )

    return {
        "ok": True,
        "message": "로그아웃 완료",
    }


@app.get("/api/me")
def me(request: Request):
    try:
        session = get_current_session(request)

        return {
            "authenticated": True,
            "username": session["username"],
        }

    except HTTPException:
        return {
            "authenticated": False,
            "username": None,
        }

@app.get("/api/stock-options")
def stock_options(session=Depends(get_current_session)):
    try:
        results = get_stock_options(limit=30)

        api_logger.info(
            f"기본 종목 목록 조회: username={session['username']}, "
            f"result_count={len(results)}"
        )

        return {
            "results": results,
        }

    except Exception as e:
        api_logger.exception(f"기본 종목 목록 조회 실패: error={e}")
        raise HTTPException(status_code=500, detail="기본 종목 목록을 불러오는 중 오류가 발생했습니다.")

@app.get("/api/stock-search")
def search_stock(q: str, session=Depends(get_current_session)):
    keyword = q.strip()

    if not keyword:
        raise HTTPException(status_code=400, detail="검색어를 입력해 주세요.")

    # 1. 내부 JSON 우선 검색
    json_results = search_json_stocks(keyword, limit=20)

    if json_results:
        api_logger.info(
            f"종목 검색(json): username={session['username']}, "
            f"q={keyword}, result_count={len(json_results)}"
        )

        return {
            "query": keyword,
            "source": "json",
            "results": json_results,
        }

    # 2. 내부 JSON에 없으면 Yahoo Finance fallback
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"

        params = {
            "q": keyword,
            "quotesCount": 10,
            "newsCount": 0,
            "listsCount": 0,
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        quotes = data.get("quotes", [])
        results = []

        for item in quotes:
            symbol = item.get("symbol")
            company = (
                item.get("shortname")
                or item.get("longname")
                or item.get("name")
            )

            quote_type = item.get("quoteType")
            exchange = item.get("exchDisp") or item.get("exchange")

            if not symbol or not company:
                continue

            if quote_type not in ["EQUITY", "ETF"]:
                continue

            results.append({
                "ticker": symbol,
                "company": company,
                "exchange": exchange,
                "quote_type": quote_type,
                "keywords": [
                    symbol,
                    company,
                ],
            })

        results = dedupe_stock_results(results)

        api_logger.info(
            f"종목 검색(yahoo): username={session['username']}, "
            f"q={keyword}, result_count={len(results)}"
        )

        return {
            "query": keyword,
            "source": "yahoo",
            "results": results,
        }

    except requests.RequestException as e:
        api_logger.warning(f"Yahoo stock search fallback failed: q={keyword}, error={e}")

        return {
            "query": keyword,
            "source": "yahoo_unavailable",
            "results": [],
            "message": "검색 결과가 없습니다. 종목명이나 티커로 다시 검색해 주세요.",
        }

@app.post("/api/run-report")
def run_report(
    payload: RunReportRequest,
    background_tasks: BackgroundTasks,
    session=Depends(get_current_session),
):
    if not payload.stocks:
        api_logger.warning(f"리포트 생성 요청 실패: 종목 없음, username={session['username']}")
        raise HTTPException(status_code=400, detail="분석할 종목이 없습니다.")

    if has_running_job(session["session_id"]):
        api_logger.warning(f"중복 리포트 생성 요청 차단: username={session['username']}")
        raise HTTPException(
            status_code=409,
            detail="이미 실행 중인 리포트 생성 작업이 있습니다.",
        )

    stock_pool = []

    for stock in payload.stocks:
        ticker = normalize_ticker_for_analysis(stock.ticker)
        company = stock.company.strip()

        if not ticker or not company:
            api_logger.warning(f"리포트 생성 요청 실패: 빈 ticker/company, username={session['username']}")
            raise HTTPException(status_code=400, detail="ticker/company 값이 비어 있습니다.")

        stock_pool.append((ticker, company))

    today_text = datetime.now().strftime("%Y-%m-%d")
    existing_reports = find_existing_daily_reports(
        stock_pool,
        today_text,
        RESULT_DIR_ABSPATH,
    )

    if existing_reports:
        existing_names = ", ".join(
            f"{item['company']}({item['ticker']})"
            for item in existing_reports
        )
        api_logger.warning(
            f"일일 리포트 중복 생성 차단: username={session['username']}, "
            f"date={today_text}, stocks={existing_names}"
        )
        raise HTTPException(
            status_code=409,
            detail=f"{today_text} 기준 리포트가 이미 있습니다: {existing_names}",
        )

    for stock in payload.stocks:
        ticker = normalize_ticker_for_analysis(stock.ticker)
        company = stock.company.strip()

        was_saved = save_stock_to_cache({
            "ticker": ticker,
            "company": company,
            "exchange": stock.exchange,
            "quote_type": stock.quote_type or "EQUITY",
            "keywords": [
                ticker,
                company,
            ],
        })

        if was_saved:
            api_logger.info(
                f"종목 cache 저장: username={session['username']}, "
                f"ticker={ticker}, company={company}"
            )

    job_id = uuid.uuid4().hex
    now_text = datetime.now().isoformat(timespec="seconds")

    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "session_id": session["session_id"],
            "username": session["username"],
            "status": "pending",
            "stocks": [
                {
                    "ticker": ticker,
                    "company": company,
                }
                for ticker, company in stock_pool
            ],
            "created_at": now_text,
            "started_at": None,
            "finished_at": None,
            "result_date": None,
            "result_dir": None,
            "report_count": 0,
            "error": None,
            "targets_status": build_targets_status_from_stocks(
                [
                    {
                        "ticker": ticker,
                        "company": company,
                    }
                    for ticker, company in stock_pool
                ],
                status="pending",
                current_step="pending",
            ),
        }

    api_logger.info(
        f"리포트 생성 요청 접수: job_id={job_id}, "
        f"username={session['username']}, stocks={stock_pool}"
    )

    background_tasks.add_task(run_report_background, job_id, stock_pool)

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "리포트 생성 작업이 시작되었습니다.",
    }


@app.get("/api/report-status/{job_id}")
def get_report_status(job_id: str, session=Depends(get_current_session)):
    job = get_owned_job(job_id, session)

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stocks": job["stocks"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "result_date": job["result_date"],
        "report_count": job["report_count"],
        "error": job["error"],
        "targets_status": job.get("targets_status") or build_targets_status_from_stocks(
            job.get("stocks", []),
            status=job.get("status"),
            current_step=job.get("status") or "pending",
            errors=[job["error"]] if job.get("error") else None,
        ),
    }


@app.get("/api/reports")
def get_report_list(session=Depends(get_current_session)):
    """result/YYYY-MM-DD 폴더 안의 마크다운 리포트 목록을 최신순으로 반환합니다."""
    if not os.path.exists(RESULT_DIR_ABSPATH):
        return {"reports": []}

    reports = []

    for date_dir in os.listdir(RESULT_DIR_ABSPATH):
        date_path = os.path.join(RESULT_DIR_ABSPATH, date_dir)

        if not os.path.isdir(date_path):
            continue

        for filename in os.listdir(date_path):
            if not filename.endswith(".md"):
                continue

            file_path = os.path.join(date_path, filename)
            modified_at = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).isoformat(timespec="minutes")
            display_name = "종합 분석 리포트" if filename == "summary.md" else filename.replace(".md", "")
            market_info = get_report_market_info(filename)
            meta_summary = build_report_list_meta_summary(date_dir, filename)

            reports.append(
                {
                    "date": date_dir,
                    "filename": filename,
                    "path": f"{date_dir}/{filename}",
                    "display_name": display_name,
                    "is_summary": filename == "summary.md",
                    "modified_at": modified_at,
                    "ticker": market_info["ticker"],
                    "company": market_info["company"],
                    "exchange": market_info["exchange"],
                    "market_label": market_info["market_label"],
                    **meta_summary,
                }
            )

    reports.sort(
        key=lambda x: (x["date"], x["is_summary"]),
        reverse=True,
    )

    return {"reports": reports}


@app.get("/api/reports/{date}/{filename}")
def get_report_detail(date: str, filename: str, session=Depends(get_current_session)):
    """특정 날짜 폴더의 마크다운 파일을 읽어서 반환합니다."""
    date = unquote(date)
    filename = unquote(filename)

    safe_date = date.replace("..", "").replace("/", "").replace("\\", "")
    safe_filename = filename.replace("..", "").replace("/", "").replace("\\", "")

    file_path = os.path.join(RESULT_DIR_ABSPATH, safe_date, safe_filename)
    abs_file_path = os.path.abspath(file_path)

    if not abs_file_path.startswith(RESULT_DIR_ABSPATH):
        api_logger.warning(
            f"잘못된 파일 경로 접근 차단: username={session['username']}, "
            f"date={date}, filename={filename}"
        )
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")

    if not os.path.exists(abs_file_path):
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")

    try:
        with open(abs_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            meta = load_report_meta(safe_date, safe_filename)

            return {
                "date": safe_date,
                "filename": safe_filename,
                "modified_at": datetime.fromtimestamp(
                    os.path.getmtime(abs_file_path)
                ).isoformat(timespec="minutes"),
                "content": content,
                "markdown": content,
                "meta": meta,
            }
    except Exception as e:
        api_logger.exception(
            f"리포트 파일 읽기 실패: username={session['username']}, "
            f"path={abs_file_path}, error={e}"
        )
        raise HTTPException(status_code=500, detail="리포트를 읽는 중 오류가 발생했습니다.")


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
