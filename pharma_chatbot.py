"""
pharma_chatbot.py — 약손: 복약안전 AI 챗봇 (터미널 버전)
================================================================
핵심 원칙:
  · 병용금기/약-음식 판단은 '챗봇의 지식'이 아니라 '도구 호출 결과'로만 한다.
    - 병용금기  -> check_interactions (공식 DUR 데이터, 결정론적)
    - 약-음식   -> 아래 FOOD_INTERACTIONS 표 (근거 있는 것만)
  · 복용 중인 약을 기억한다.
  · 일반 질문(효능/부작용/건강)도 답하되, 불확실하면 약사 상담 권고.
  · 모든 답변은 '의료행위가 아닌 정보 제공'이며 약사·의사 상담을 권한다.

실행:
  python pharma_chatbot.py          <- 사람이 직접 대화
  python pharma_chatbot.py --demo   <- 미리 짠 질문으로 자동 시연(테스트용)
================================================================
"""

import os
import sys
import re
import json
import base64
from itertools import combinations

from dotenv import load_dotenv
from anthropic import Anthropic

from dur_agent_starter import (
    load_contraindications, load_product_index,
    resolve_drug, check_interactions,
)

CSV = "한국의약품안전관리원_병용금기약물_20240625.csv"
MODEL = "claude-sonnet-5"

load_dotenv()   # .env 에서 ANTHROPIC_API_KEY 를 읽어와 환경변수로 올린다 (이게 있어야 Claude 인증됨)


# ── 윈도우 터미널에서 이모지 때문에 안 죽도록 안전 출력 ───────────
def safe_print(*args):
    enc = sys.stdout.encoding or "utf-8"
    text = " ".join(str(a) for a in args)
    sys.stdout.write(text.encode(enc, errors="replace").decode(enc) + "\n")
    sys.stdout.flush()


# ── 약-음식 상호작용 표 (근거가 분명한 대표 사례만) ──────────────
# 약키워드(한글/영문 아무거나 이름에 들어있으면 매칭) -> 음식 + 이유
FOOD_INTERACTIONS = [
    {"약키워드": ["와파린", "warfarin", "쿠마딘"],
     "음식": "비타민K가 많은 음식(시금치·케일·낫토 등)",
     "설명": "혈액을 묽게 하는 효과가 들쑥날쑥해질 수 있어요. 갑자기 많이/적게 먹지 말고 평소처럼 일정하게 드세요."},
    {"약키워드": ["심바스타틴", "simvastatin", "아토르바", "atorvastatin", "스타틴"],
     "음식": "자몽·자몽주스",
     "설명": "약이 몸에 과하게 쌓여 근육이 손상될 위험이 커질 수 있어요."},
    {"약키워드": ["암로디핀", "amlodipine", "펠로디핀", "felodipine", "니페디핀"],
     "음식": "자몽·자몽주스",
     "설명": "혈압이 지나치게 떨어질 수 있어요."},
    {"약키워드": ["타이레놀", "아세트아미노펜", "acetaminophen"],
     "음식": "술(알코올)",
     "설명": "간에 부담이 커질 수 있어요."},
    {"약키워드": ["메트포르민", "metformin"],
     "음식": "과도한 음주",
     "설명": "저혈당이나 젖산증 위험이 커질 수 있어요."},
    {"약키워드": ["테트라사이클린", "tetracycline", "시프로", "ciprofloxacin", "퀴놀론"],
     "음식": "우유·유제품·칼슘제",
     "설명": "약 흡수가 줄어 효과가 떨어질 수 있어요. 복용 시간을 2시간 이상 벌리세요."},
]


# ============================================================
# 데이터 로드 (프로그램 시작 시 한 번)
# ============================================================
safe_print("복약안전 데이터 불러오는 중... (파일이 커서 10~20초 걸려요)")
PARTNERS, NAME_OF = load_contraindications(CSV)
PRODUCT_TO_CODE = load_product_index(CSV)
safe_print(f"준비 완료 (금기 성분 {len(PARTNERS):,} · 제품명 {len(PRODUCT_TO_CODE):,})\n")

# 사용자의 '복용 중인 약'을 기억하는 메모리
STATE = {"current_meds": []}


# ============================================================
# 도구(tool)로 쓸 파이썬 함수들
# ============================================================
def _resolve(name):
    """약 이름 -> (성분코드, 인식된 제품명). 못 찾으면 None."""
    r = resolve_drug(name, PRODUCT_TO_CODE, score_cutoff=60)
    return r  # {'매칭품목','성분코드','신뢰도',...} 또는 None


def tool_remember_medications(drug_names):
    """복용 중인 약 목록을 기억한다."""
    for n in drug_names:
        if n not in STATE["current_meds"]:
            STATE["current_meds"].append(n)
    return {"저장된_복용약": STATE["current_meds"]}


def tool_check_interactions(drug_names=None):
    """
    약 이름들 -> 성분코드 변환 -> check_interactions(공식 데이터)로 병용금기 판정.
    drug_names가 비면 기억된 복용약을 사용.
    """
    names = drug_names or STATE["current_meds"]
    if len(names) < 2:
        return {"안내": "비교하려면 약이 최소 2개 필요해요.", "현재약": names}

    resolved, not_found = [], []
    for n in names:
        r = _resolve(n)
        if r:
            resolved.append({"입력": n, "제품명": r["매칭품목"], "성분코드": r["성분코드"]})
        else:
            not_found.append(n)

    codes = [x["성분코드"] for x in resolved]
    alerts = check_interactions(codes, PARTNERS, NAME_OF)   # ★ 안전 코어(결정론적)

    return {
        "검사한_약": [x["입력"] for x in resolved],
        "데이터에서_못찾은_약": not_found,
        "병용금기_건수": len(alerts),
        "병용금기_목록": [
            {"성분A": a["성분A"], "성분B": a["성분B"], "이유": a["금기사유"]}
            for a in alerts
        ],
    }


def tool_check_food(drug_names=None):
    """약 이름들 -> 대표적인 '같이 먹으면 안 좋은 음식' 안내."""
    names = drug_names or STATE["current_meds"]
    hits, unknown = [], []
    for n in names:
        low = n.lower()
        matched = [
            {"약": n, "주의음식": item["음식"], "이유": item["설명"]}
            for item in FOOD_INTERACTIONS
            if any(k.lower() in low for k in item["약키워드"])
        ]
        if matched:
            hits.extend(matched)
        else:
            unknown.append(n)
    return {
        "주의할_음식": hits,
        "정보없는_약": unknown,   # 표에 없는 약은 단정 금지 -> 약사 상담 안내
    }


def extract_drugs_from_image(image_bytes, media_type="image/jpeg"):
    """약봉투/처방전 사진 -> 약 이름 리스트 (Claude 비전). client/MODEL 재사용."""
    b64 = base64.standard_b64encode(image_bytes).decode()
    prompt = (
        "이 사진은 약봉투 또는 처방전이다. 적혀 있는 '약 이름'을 모두 찾아라. "
        "가능하면 용량(예: 250mg)도 약 이름 뒤에 붙여라. "
        '오직 JSON 배열만 출력하라. 예: ["클래리시드정250mg", "브릴린타정90mg"]. '
        "약 이름이 안 보이면 빈 배열 [] 만 출력하라."
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=800,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                          "media_type": media_type, "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\[.*\]", text, re.DOTALL)      # ```json 감싸도 안전 추출
    try:
        return json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []


# ── Claude에게 알려줄 도구 설명서(스키마) ───────────────────────
TOOLS = [
    {
        "name": "remember_medications",
        "description": "사용자가 현재 복용 중이라고 말한 약 이름들을 기억한다.",
        "input_schema": {
            "type": "object",
            "properties": {"drug_names": {"type": "array", "items": {"type": "string"},
                                          "description": "복용 중인 약 이름 목록"}},
            "required": ["drug_names"],
        },
    },
    {
        "name": "check_interactions",
        "description": ("두 개 이상의 약이 서로 병용금기인지 공식 DUR 데이터로 판정한다. "
                        "약을 함께 먹어도 되는지 묻는 모든 질문에 반드시 이 도구를 써라. "
                        "네 지식으로 금기 여부를 지어내지 마라. drug_names를 비우면 기억된 복용약으로 검사한다."),
        "input_schema": {
            "type": "object",
            "properties": {"drug_names": {"type": "array", "items": {"type": "string"},
                                          "description": "검사할 약 이름들(생략 가능)"}},
        },
    },
    {
        "name": "check_food",
        "description": ("특정 약과 '같이 먹으면 안 좋은 음식'을 표에서 찾아 안내한다. "
                        "음식/식이 관련 질문에 이 도구를 써라. 표에 없으면 단정하지 말 것."),
        "input_schema": {
            "type": "object",
            "properties": {"drug_names": {"type": "array", "items": {"type": "string"},
                                          "description": "확인할 약 이름들(생략 가능)"}},
        },
    },
]

DISPATCH = {
    "remember_medications": lambda i: tool_remember_medications(i.get("drug_names", [])),
    "check_interactions":   lambda i: tool_check_interactions(i.get("drug_names")),
    "check_food":           lambda i: tool_check_food(i.get("drug_names")),
}


SYSTEM = """너는 '약손'이라는 복약안전 안내 도우미다. 한국어로, 어르신도 이해하기 쉽게 말한다.

반드시 지켜라:
1) 두 약을 같이 먹어도 되는지 등 '병용금기' 판단은 절대 스스로 하지 말고 check_interactions 도구를 호출해 그 결과로만 답하라.
2) 약과 음식 관련 질문은 check_food 도구를 호출해 그 결과로만 답하라.
3) 도구 결과에 없는 금기나 위험을 새로 지어내지 마라. 결과가 '금기 없음'이면 그대로 안내하라.
4) 사용자가 복용 중인 약을 말하면 remember_medications 도구로 기억하라.
5) 일반적인 약 효능·부작용·건강 질문은 아는 범위에서 답하되, 확실하지 않으면 단정하지 말고 약사 상담을 권하라.
6) 너는 의료행위를 하는 것이 아니라 정보를 제공한다. 모든 답변의 마지막에 '정확한 판단은 약사·의사와 상담하세요'라는 취지의 문장을 자연스럽게 덧붙여라.
7) 이모지는 쓰지 마라(일부 화면에서 깨진다)."""


# ============================================================
# 대화 한 턴 처리 (도구 호출 자동 반복)
# ============================================================
client = Anthropic()
messages = []   # 대화 기록 = Claude가 맥락을 기억하는 방법


def chat(user_text):
    messages.append({"role": "user", "content": user_text})
    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=1024,
            system=SYSTEM, tools=TOOLS, messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            # 도구를 더 안 부르면 = 최종 답변
            return "".join(b.text for b in resp.content if b.type == "text")

        # Claude가 도구를 부름 -> 파이썬 함수 실행 후 결과를 돌려줌
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = DISPATCH[b.name](b.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(out, ensure_ascii=False),
                })
        messages.append({"role": "user", "content": results})


# ============================================================
# 실행부
# ============================================================
DEMO_QUESTIONS = [
    "제가 지금 클래리시드정하고 브릴린타정을 같이 먹고 있어요. 같이 먹어도 괜찮아요?",
    "저는 와파린도 복용 중이에요. 조심해야 할 음식이 있을까요?",
    "타이레놀은 어떤 약이고 흔한 부작용은 뭐예요?",
    "제가 지금 먹는 약들 통틀어서 위험한 조합 있는지 다시 확인해줄래요?",
]


def main():
    if "--demo" in sys.argv:
        safe_print("=== 자동 시연 모드 ===")
        for q in DEMO_QUESTIONS:
            safe_print("\n[나]   " + q)
            safe_print("[약손] " + chat(q))
        return

    safe_print("=== 약손 챗봇 (종료: quit) ===")
    while True:
        try:
            q = input("\n[나] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit", "종료", ""):
            break
        safe_print("[약손] " + chat(q))
    safe_print("\n대화를 마칩니다. 건강하세요.")


if __name__ == "__main__":
    main()
