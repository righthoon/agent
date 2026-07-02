"""
api_server.py — 약속 챗봇 API 서버 (FastAPI)
================================================================
팀원 앱이 POST로 질문+복용약을 보내면, 챗봇 답변을 JSON으로 돌려준다.
화면(Streamlit) 없음. 병용금기 도구 호출 로직은 그대로 유지된다.

실행:  uvicorn api_server:app --reload --port 8000
테스트 화면(자동 생성):  http://localhost:8000/docs
================================================================
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chatbot_core as cc   # 기존 챗봇/병용금기 로직 그대로 재사용

app = FastAPI(title="약속 챗봇 API", version="1.0")

# 팀원의 웹앱(다른 주소)에서도 호출할 수 있게 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ---- 요청(request) 모양 ----
class Turn(BaseModel):
    role: str        # "user" 또는 "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str                 # 사용자의 질문 (필수)
    meds: list[str] = []         # 복용 중인 약 이름 목록 (선택)
    history: list[Turn] = []     # 이전 대화 (선택, 여러 번 주고받을 때)


# ---- 응답(response) 모양 ----
class ChatResponse(BaseModel):
    answer: str                  # 챗봇 답변
    meds: list[str]              # 사용된 복용약 목록(확인용)


@app.get("/")
def root():
    """서버 살아있는지 확인용."""
    return {"status": "ok", "usage": "POST /chat 에 {message, meds} 를 보내세요"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """질문(+복용약, +이전대화) -> 챗봇 답변(JSON)."""
    try:
        messages = [{"role": t.role, "content": t.content} for t in req.history]
        messages.append({"role": "user", "content": req.message})
        answer = cc.get_chatbot_response(messages, req.meds)   # ★ 병용금기 도구 포함
        return {"answer": answer, "meds": req.meds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
