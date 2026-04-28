import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI-Reinvest API Server")

# React 프론트엔드(localhost:3000)에서 백엔드(localhost:8000)를 호출할 수 있도록 CORS 허용
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
    """result 폴더에 있는 마크다운 파일 목록을 최신순으로 반환합니다."""
    if not os.path.exists(RESULT_DIR_ABSPATH):
        return {"reports": []}
    
    files = [f for f in os.listdir(RESULT_DIR_ABSPATH) if f.endswith(".md")]
    files.sort(reverse=True) # 최신 날짜가 위로 오도록 정렬
    
    reports = [{"filename": f, "date": f.replace(".md", "")} for f in files]
    return {"reports": reports}

@app.get("/api/reports/{filename}")
def get_report_detail(filename: str):
    """특정 마크다운 파일의 내용을 읽어서 반환합니다."""
    # 💡 보안 강화: 파일 경로 조작(Path Traversal) 공격 방지
    safe_filename = filename.replace("..", "")
    file_path = os.path.join(RESULT_DIR_ABSPATH, safe_filename)
    
    if not os.path.abspath(file_path).startswith(RESULT_DIR_ABSPATH):
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {"filename": filename, "content": f.read()}
    except Exception:
        raise HTTPException(status_code=500, detail="리포트를 읽는 중 오류가 발생했습니다.")

if __name__ == "__main__":
    # python api.py 로 직접 실행할 때 uvicorn 서버를 구동하도록 설정
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)