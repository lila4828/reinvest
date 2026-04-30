import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import unquote

app = FastAPI(title="AI-Reinvest API Server")

app.add_middleware( 
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULT_DIR = "result"
RESULT_DIR_ABSPATH = os.path.abspath(RESULT_DIR)


@app.get("/api/reports")
def get_report_list():
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

            # summary.md를 대표 리포트로 우선 표시
            display_name = "종합 분석 리포트" if filename == "summary.md" else filename.replace(".md", "")

            reports.append(
                {
                    "date": date_dir,
                    "filename": filename,
                    "path": f"{date_dir}/{filename}",
                    "display_name": display_name,
                    "is_summary": filename == "summary.md",
                }
            )

    reports.sort(
        key=lambda x: (x["date"], x["is_summary"]),
        reverse=True,
    )

    return {"reports": reports}


@app.get("/api/reports/{date}/{filename}")
def get_report_detail(date: str, filename: str):
    """특정 날짜 폴더의 마크다운 파일을 읽어서 반환합니다."""
    date = unquote(date)
    filename = unquote(filename)

    safe_date = date.replace("..", "").replace("/", "").replace("\\", "")
    safe_filename = filename.replace("..", "").replace("/", "").replace("\\", "")

    file_path = os.path.join(RESULT_DIR_ABSPATH, safe_date, safe_filename)
    abs_file_path = os.path.abspath(file_path)

    if not abs_file_path.startswith(RESULT_DIR_ABSPATH):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")

    if not os.path.exists(abs_file_path):
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")

    try:
        with open(abs_file_path, "r", encoding="utf-8") as f:
            return {
                "date": safe_date,
                "filename": safe_filename,
                "content": f.read(),
            }
    except Exception:
        raise HTTPException(status_code=500, detail="리포트를 읽는 중 오류가 발생했습니다.")


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)