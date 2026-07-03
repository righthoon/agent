"""
api_server.py — 약속 API 서버 (FastAPI)
================================================================
프론트엔드(약속_app.html)가 호출하는 모든 엔드포인트를 제공한다.
  · POST /api/patients          환자 등록
  · POST /api/ocr/text          텍스트 -> 약 추가
  · POST /api/ocr/image         사진 -> 약 추가 (Claude 비전)
  · GET  /api/ocr/{patient_id}  약 목록 조회
  · POST /api/analyze           병용금기 검사
  · POST /api/speech/transcribe 음성 -> 텍스트 (OpenAI Whisper)
  · POST /chat                  챗봇 (기존)

실행:  uvicorn api_server:app --host 0.0.0.0 --port 8000
문서:  http://localhost:8000/docs
================================================================
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import chatbot_core as cc                          # 데이터/챗봇/도구 재사용
from dur_agent_starter import resolve_drug, check_interactions
from datetime import datetime, timezone

app = FastAPI(title="약속 API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# 간단한 인메모리 저장소 (데모용 — 서버 재시작 시 초기화)
PATIENTS = {}
_counter = {"n": 0}
_drug_seq = {"n": 0}


def _new_id():
    _counter["n"] += 1
    return f"p{_counter['n']}"


def _match_drug(info):
    """Claude 추출 정보(dict) -> HIRA(DUR) 성분코드 매칭."""
    name = str(info.get("약품명") or "").strip()
    ingr = str(info.get("성분명") or "").strip()
    r = resolve_drug(name, cc._PRODUCT_TO_CODE, score_cutoff=60) if name else None
    if not r and ingr:
        r = resolve_drug(ingr, cc._PRODUCT_TO_CODE, score_cutoff=60)
    if r:
        code = r["성분코드"]
        status = "matched" if r["신뢰도"] >= 80 else "ambiguous"
        return {"ingr_code": code, "ingr_name": cc._NAME_OF.get(code, ""),
                "product_name": r["매칭품목"], "company": "", "match": status}
    return {"ingr_code": None, "ingr_name": None,
            "product_name": (name or ingr), "company": None, "match": "not_found"}


def _make_row(info, patient_id, input_type):
    """추출 정보 + 매칭 -> 저장 row (내부에 원문 _info 보관)."""
    m = _match_drug(info)
    _drug_seq["n"] += 1
    return {
        "id": _drug_seq["n"], "patient_id": patient_id,
        "ingr_code": m["ingr_code"], "ingr_name": m["ingr_name"],
        "product_name": m["product_name"],
        "efficacy_group": str(info.get("효능군") or ""),
        "prescribing_dept": str(info.get("처방과") or ""),
        "company": m["company"], "source_text": str(info.get("성분명") or ""),
        "input_type": input_type, "match_status": m["match"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_info": info,
    }


def _post_item(row):
    """POST 응답 형식 (한글 키 + match + collected_drug_id)."""
    info = row["_info"]
    keys = ["약품명", "성분명", "효능군", "처방과", "낱알_모양", "낱알_색상",
            "낱알_각인_앞", "낱알_각인_뒤", "낱알_분할선_앞", "낱알_분할선_뒤"]
    item = {k: str(info.get(k) or "") for k in keys}
    item.update({"product_name": row["product_name"], "source_text": row["source_text"],
                 "ingr_code": row["ingr_code"], "ingr_name": row["ingr_name"],
                 "company": row["company"], "match": row["match_status"],
                 "collected_drug_id": row["id"]})
    return item


def _raw_row(row):
    """GET 응답 형식 (raw DB row, _info 제외)."""
    return {k: v for k, v in row.items() if k != "_info"}


def _add_from_infos(patient, infos, input_type):
    rows = [_make_row(info, patient["id"], input_type) for info in infos]
    patient["drugs"].extend(rows)
    return [_post_item(r) for r in rows]


def _get_patient(pid):
    p = PATIENTS.get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없어요. 다시 시작해 주세요.")
    return p


# ============================================================
# 환자 등록
# ============================================================
class PatientReq(BaseModel):
    last_name: str
    age: int
    underlying_conditions: list[str] = []


@app.post("/api/patients")
def create_patient(req: PatientReq):
    pid = _new_id()
    patient = {"id": pid, "last_name": req.last_name, "age": req.age,
               "underlying_conditions": req.underlying_conditions, "drugs": []}
    PATIENTS[pid] = patient
    return patient


# ============================================================
# 약 추가 (텍스트 / 사진) + 목록 조회
# ============================================================
class TextReq(BaseModel):
    patient_id: str
    text: str


@app.post("/api/ocr/text")
def ocr_text(req: TextReq):
    patient = _get_patient(req.patient_id)
    infos = cc.extract_drug_info_from_text(req.text)     # 구조화 추출
    return {"drugs": _add_from_infos(patient, infos, "text")}


@app.post("/api/ocr/image")
async def ocr_image(patient_id: str = Form(...), extra_text: str = Form(""),
                    file: UploadFile = File(...)):
    patient = _get_patient(patient_id)
    data = await file.read()
    media = file.content_type or "image/jpeg"
    infos = cc.extract_drug_info_from_image(data, media, extra_text)   # Claude 비전
    return {"drugs": _add_from_infos(patient, infos, "image")}


@app.get("/api/ocr/{patient_id}")
def list_drugs(patient_id: str):
    return {"drugs": [_raw_row(r) for r in _get_patient(patient_id)["drugs"]]}


# ============================================================
# 병용금기 검사
# ============================================================
class AnalyzeReq(BaseModel):
    patient_id: str


@app.post("/api/analyze")
def analyze(req: AnalyzeReq):
    patient = _get_patient(req.patient_id)
    codes = [d["ingr_code"] for d in patient["drugs"] if d.get("ingr_code")]
    alerts = check_interactions(codes, cc._PARTNERS, cc._NAME_OF)   # ★ 공식 데이터 판정
    return {
        "병용금기_flag": len(alerts) > 0,
        "병용금기": [{"해당약물": [a["성분A"], a["성분B"]], "상세정보": a["금기사유"]}
                  for a in alerts],
        # 아래 항목들은 별도 데이터가 필요해 현재는 미판정(false)
        "동일성분중복_flag": False, "중복처방_교차처방과_flag": False,
        "노인주의약물_flag": False, "주의해열진통제_flag": False,
        "연령금기_flag": False, "효능군중복_flag": False,
    }


# ============================================================
# 음성 -> 텍스트 (OpenAI Whisper) [브라우저 미지원 시 폴백]
# ============================================================
_oai = {"client": None}


def _openai():
    if _oai["client"] is None:
        from openai import OpenAI
        _oai["client"] = OpenAI()          # OPENAI_API_KEY 필요
    return _oai["client"]


@app.post("/api/speech/transcribe")
async def transcribe(patient_id: str = Form(...), auto_parse: str = Form("true"),
                     file: UploadFile = File(...)):
    patient = _get_patient(patient_id)
    audio = await file.read()
    try:
        tr = _openai().audio.transcriptions.create(
            model="whisper-1", file=(file.filename or "audio.webm", audio), language="ko")
        text = tr.text
    except Exception as e:
        raise HTTPException(status_code=500, detail="음성 인식 실패: " + str(e))
    result = {"text": text}
    if auto_parse == "true" and text.strip():
        infos = cc.extract_drug_info_from_text(text)
        if infos:
            result["drugs"] = _add_from_infos(patient, infos, "voice")   # ocr와 동일 형식
    return result


# ============================================================
# 챗봇 (기존)
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


@app.get("/")
def root():
    return {"status": "ok", "app": "약속 API",
            "endpoints": ["/api/patients", "/api/ocr/text", "/api/ocr/image",
                          "/api/ocr/{id}", "/api/analyze", "/api/speech/transcribe", "/chat"]}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        messages = [{"role": t.role, "content": t.content} for t in req.history]
        messages.append({"role": "user", "content": req.message})
        answer = cc.get_chatbot_response(messages, req.meds)
        return {"answer": answer, "meds": req.meds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 'python api_server.py' 로 직접 실행할 때도 Railway의 PORT 환경변수를 사용
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
