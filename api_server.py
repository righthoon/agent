"""
api_server.py — 약속 챗봇 API 서버 (FastAPI)
================================================================
'약속' 앱은 백엔드를 2개로 나눠 쓴다.
  1) VLM 저장소(https://web-production-bf56f.up.railway.app)
     — 환자 등록 / 사진·텍스트·음성으로 약 입력 / 병용금기 분석
  2) 이 서버(api_server.py)
     — POST /chat   챗봇(병용금기·약-음식 상호작용 등 복약 질문 응답)
     — GET  /       프론트엔드(약속_app.html) 서빙

두 서버 주소는 약속_app.html 안에 기본값으로 박혀 있고, 필요하면 앱의
'내 정보' 탭에서 바꿔볼 수 있다.

실행:  uvicorn api_server:app --host 0.0.0.0 --port 8000
문서:  http://localhost:8000/docs
================================================================
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import chatbot_core as cc                          # 데이터/챗봇/도구 재사용

app = FastAPI(title="약속 챗봇 API", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_HTML_PATH = Path(__file__).resolve().parent / "약속_app.html"


# ============================================================
# 챗봇
# ============================================================
class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    meds: list[str] = []
    history: list[Turn] = []


class ChatResponse(BaseModel):
    answer: str
    meds: list[str]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        messages = [{"role": t.role, "content": t.content} for t in req.history]
        messages.append({"role": "user", "content": req.message})
        answer = cc.get_chatbot_response(messages, req.meds)
        return {"answer": answer, "meds": req.meds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 프론트엔드 서빙 + 헬스체크
# ============================================================
@app.get("/")
def root():
    return FileResponse(_HTML_PATH)


@app.get("/health")
def health():
    return {"status": "ok", "app": "약속 챗봇 API", "endpoints": ["/", "/chat"]}


# 'python api_server.py' 로 직접 실행할 때도 Railway의 PORT 환경변수를 사용
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
