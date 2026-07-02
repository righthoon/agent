"""
chatbot_core.py — 화면과 분리된 복약안전 챗봇 '부품'
================================================================
다른 앱(팀원 앱 포함)에서 쓰는 법:

    from chatbot_core import get_chatbot_response

    messages = [{"role": "user", "content": "내 약들 같이 먹어도 돼?"}]
    meds = ["클래리시드정", "브릴린타정"]
    answer = get_chatbot_response(messages, meds)   # -> 답변(문자열)

  · messages : [{"role":"user"/"assistant", "content":"글자"}] 형태의 대화 기록
  · meds     : 복용 중인 약 이름 목록(문자열 리스트). 없으면 [] 또는 생략
  · 반환값   : 챗봇 답변 문자열

필요 파일 : dur_agent_starter.py, 병용금기 CSV, .env(ANTHROPIC_API_KEY)
필요 패키지: anthropic, python-dotenv, rapidfuzz
================================================================
"""

import os
import re
import json
import base64

from dotenv import load_dotenv
from anthropic import Anthropic

from dur_agent_starter import (
    load_contraindications, load_product_index, resolve_drug, check_interactions,
)

# ── 준비: 모듈을 처음 import 할 때 딱 한 번 실행 ──────────────
load_dotenv()                                  # .env 에서 API 키 로드
CSV = "한국의약품안전관리원_병용금기약물_20240625.csv"
MODEL = "claude-sonnet-5"

def _load_data():
    """배포용: 작은 dur_data.json 이 있으면 그걸 쓰고, 없으면 원본 CSV를 읽는다."""
    if os.path.exists("dur_data.json"):
        with open("dur_data.json", encoding="utf-8") as f:
            d = json.load(f)
        partners = {code: set((p, r) for p, r in pairs)
                    for code, pairs in d["partners"].items()}
        return partners, d["name_of"], d["product_to_code"]
    # 로컬 개발용 폴백 (원본 CSV)
    partners, name_of = load_contraindications(CSV)
    return partners, name_of, load_product_index(CSV)


_PARTNERS, _NAME_OF, _PRODUCT_TO_CODE = _load_data()   # 병용금기 데이터(JSON 우선)
_client = Anthropic()                                  # 키는 위 load_dotenv 로 자동 인증

# ── 약-음식 상호작용 표 (근거 분명한 대표 사례만) ─────────────
_FOOD = [
    {"약키워드": ["와파린", "warfarin", "쿠마딘"],
     "음식": "비타민K가 많은 음식(시금치·케일·낫토 등)",
     "설명": "혈액을 묽게 하는 효과가 들쭉날쭉해질 수 있어요. 평소처럼 일정하게 드세요."},
    {"약키워드": ["심바스타틴", "simvastatin", "아토르바", "atorvastatin", "스타틴"],
     "음식": "자몽·자몽주스", "설명": "약이 몸에 과하게 쌓여 근육 손상 위험이 커질 수 있어요."},
    {"약키워드": ["암로디핀", "amlodipine", "펠로디핀", "felodipine", "니페디핀"],
     "음식": "자몽·자몽주스", "설명": "혈압이 지나치게 떨어질 수 있어요."},
    {"약키워드": ["타이레놀", "아세트아미노펜", "acetaminophen"],
     "음식": "술(알코올)", "설명": "간에 부담이 커질 수 있어요."},
    {"약키워드": ["메트포르민", "metformin"],
     "음식": "과도한 음주", "설명": "저혈당이나 젖산증 위험이 커질 수 있어요."},
    {"약키워드": ["테트라사이클린", "tetracycline", "시프로", "ciprofloxacin", "퀴놀론"],
     "음식": "우유·유제품·칼슘제", "설명": "약 흡수가 줄어 효과가 떨어질 수 있어요. 복용 간격을 2시간 이상 두세요."},
]


# ============================================================
# 공개 helper — 화면(②검사)이나 다른 코드에서도 재사용 가능
# ============================================================
def check_meds(meds):
    """복용약 이름 목록 -> 병용금기 판정 결과(dict)."""
    if len(meds) < 2:
        return {"안내": "약이 2개 이상 필요해요.", "병용금기_건수": 0,
                "병용금기_목록": [], "데이터에서_못찾은_약": []}
    codes, not_found = [], []
    for n in meds:
        r = resolve_drug(n, _PRODUCT_TO_CODE, score_cutoff=60)
        if r:
            codes.append(r["성분코드"])
        else:
            not_found.append(n)
    alerts = check_interactions(codes, _PARTNERS, _NAME_OF)      # ★ 결정론적 안전 코어
    return {
        "병용금기_건수": len(alerts),
        "병용금기_목록": [{"성분A": a["성분A"], "성분B": a["성분B"], "이유": a["금기사유"]}
                     for a in alerts],
        "데이터에서_못찾은_약": not_found,
    }


def check_food(meds):
    """복용약 이름 목록 -> 같이 먹으면 안 좋은 음식(dict)."""
    hits, unknown = [], []
    for n in meds:
        low = n.lower()
        matched = [{"약": n, "주의음식": it["음식"], "이유": it["설명"]}
                   for it in _FOOD if any(k.lower() in low for k in it["약키워드"])]
        if matched:
            hits.extend(matched)
        else:
            unknown.append(n)
    return {"주의할_음식": hits, "정보없는_약": unknown}


def extract_drugs_from_image(image_bytes, media_type="image/jpeg"):
    """약봉투/처방전 사진 -> 약 이름 리스트 (Claude 비전)."""
    b64 = base64.standard_b64encode(image_bytes).decode()
    prompt = (
        "이 사진은 약봉투 또는 처방전이다. 적혀 있는 '약 이름'을 모두 찾아라. "
        "가능하면 용량(예: 250mg)도 약 이름 뒤에 붙여라. "
        '오직 JSON 배열만 출력하라. 예: ["클래리시드정250mg", "브릴린타정90mg"]. '
        "약 이름이 안 보이면 빈 배열 [] 만 출력하라."
    )
    resp = _client.messages.create(
        model=MODEL, max_tokens=800,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                          "media_type": media_type, "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\[.*\]", text, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []


# ── Claude 도구 설명서 + 규칙 ───────────────────────────────
_TOOLS = [
    {
        "name": "check_interactions",
        "description": ("두 개 이상의 약이 서로 병용금기인지 공식 DUR 데이터로 판정한다. "
                        "약을 함께 먹어도 되는지 묻는 질문에 반드시 이 도구를 써라. "
                        "drug_names를 비우면 사용자의 현재 복용약으로 검사한다."),
        "input_schema": {"type": "object", "properties": {
            "drug_names": {"type": "array", "items": {"type": "string"}}}},
    },
    {
        "name": "check_food",
        "description": ("특정 약과 '같이 먹으면 안 좋은 음식'을 표에서 찾아 안내한다. "
                        "표에 없으면 단정하지 말 것. drug_names를 비우면 현재 복용약으로 확인한다."),
        "input_schema": {"type": "object", "properties": {
            "drug_names": {"type": "array", "items": {"type": "string"}}}},
    },
]

_SYSTEM_BASE = """너는 '약속'이라는 복약안전 안내 도우미다. 한국어로, 어르신도 이해하기 쉽게 말한다.

반드시 지켜라:
1) 병용금기(같이 먹어도 되는지) 판단은 절대 스스로 하지 말고 check_interactions 도구 결과로만 답하라.
2) 약-음식 질문은 check_food 도구 결과로만 답하라.
3) 도구 결과에 없는 위험을 새로 지어내지 마라. 결과가 '금기 없음'이면 그대로 안내하라.
4) 사용자의 현재 복용약은 이 지시문 맨 아래에 제공된다. "내 약들"이라고 물으면 drug_names 없이 도구를 호출하라.
5) 일반 약 효능·부작용·건강 질문은 아는 범위에서 답하되, 확실하지 않으면 약사 상담을 권하라.
6) 너는 의료행위가 아니라 정보 제공을 한다. 모든 답변 끝에 '정확한 판단은 약사·의사와 상담하세요' 취지 문장을 자연스럽게 붙여라."""


# ============================================================
# ★ 다른 앱에서 갖다 쓸 메인 함수
# ============================================================
def get_chatbot_response(messages, meds=None):
    """
    대화 기록(messages) + 복용약 목록(meds) -> 챗봇 답변(문자열).
    · 입력을 바꾸지 않는다(복사해서 사용). 반환된 답변은 호출한 앱이 기록에 추가하면 된다.
    """
    meds = list(meds or [])
    convo = [dict(m) for m in messages]        # 원본 보호용 복사
    system = _SYSTEM_BASE + f"\n\n[사용자가 현재 복용 중인 약]: {meds if meds else '아직 없음'}"

    def dispatch(name, inp):
        names = inp.get("drug_names") or meds
        if name == "check_interactions":
            return check_meds(names)
        if name == "check_food":
            return check_food(names)
        return {}

    while True:
        resp = _client.messages.create(
            model=MODEL, max_tokens=1024,
            system=system, tools=_TOOLS, messages=convo,
        )
        convo.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(dispatch(b.name, b.input), ensure_ascii=False)})
        convo.append({"role": "user", "content": results})
