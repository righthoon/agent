"""
약손 - AI 복약안전 에이전트 스타터
================================================================
설계 원칙 (이대로 발표하면 기술심층 점수 방어됨):
  ① 병용금기 '판정'은 결정론적 룰엔진.  RAG/embedding 아님.  (안전 코어)
  ② 약 이름 정규화에만 fuzzy/embedding 사용.
  ③ 챗봇 일반 질문에만 RAG(embedding) 사용.
  ④ LangGraph가 위 셋을 묶는 agent workflow (챗봇 이상).

필요 패키지:
  pip install rapidfuzz langgraph langchain-anthropic anthropic
데이터(공공데이터포털, 무료):
  - DUR 병용금기 파일  -> data/dur_contraindication.csv
  - 품목-성분 마스터    -> data/drug_master.csv
  - e약은요(챗봇 RAG용) -> data/edrug_info.csv (선택)
================================================================
"""

import csv
from itertools import combinations
from rapidfuzz import process, fuzz


# ============================================================
# ① 데이터 로드
# ============================================================
def _detect_encoding(csv_path):
    """
    한국 공공데이터 CSV는 utf-8이 아니라 cp949(euc-kr)인 경우가 많다.
    앞부분을 시험 삼아 디코딩해서 되는 인코딩을 찾아 돌려준다.
    (utf-8 먼저 시도 → 실패하면 cp949)
    """
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(csv_path, encoding=enc) as f:
                f.read(4096)          # 앞 4KB만 미리 읽어 확인
            return enc
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1,
                             "utf-8/cp949 둘 다 실패 — 파일 인코딩을 확인하세요")


def load_contraindications(csv_path):
    """
    한국의약품안전관리원_병용금기약물 CSV 로드.
    이 파일은 '한 줄 = 금기 한 쌍' 구조라, 성분코드1 <-> 성분코드2를 그대로 짝으로 쓴다.
    (따로 조합할 필요 없음)
    반환:
      partners: { 성분코드 -> set((상대성분코드, 금기사유)) }
      name_of : { 성분코드 -> 성분명 }   # 사람이 읽을 표시용
    """
    partners = {}
    name_of = {}
    enc = _detect_encoding(csv_path)          # utf-8 안 되면 cp949 자동 선택
    with open(csv_path, encoding=enc) as f:
        reader = csv.DictReader(f)
        # 금기사유가 담긴 컬럼 이름은 파일마다 조금 달라서 자동 탐색
        reason_col = next((c for c in ["금기내용", "상세정보", "비고", "금기사유"]
                           if reader.fieldnames and c in reader.fieldnames), None)
        for row in reader:
            a = row["성분코드1"].strip()
            b = row["성분코드2"].strip()
            reason = (row.get(reason_col, "") if reason_col else "").strip()
            partners.setdefault(a, set()).add((b, reason))
            partners.setdefault(b, set()).add((a, reason))
            name_of[a] = row.get("성분명1", a).strip()
            name_of[b] = row.get("성분명2", b).strip()
    return partners, name_of


def load_drug_master(csv_path):
    """ 품목명 -> 성분코드 매핑 (식약처 허가정보/DUR 성분정보로 구성). """
    name_to_ingredient = {}
    enc = _detect_encoding(csv_path)
    with open(csv_path, encoding=enc) as f:
        for row in csv.DictReader(f):
            name_to_ingredient[row["품목명"].strip()] = row["성분코드"].strip()
    return name_to_ingredient


def load_product_index(csv_path):
    """
    병용금기 CSV에서 '제품명 -> 성분코드' 매핑을 만든다.
    제품명1/성분코드1, 제품명2/성분코드2 양쪽을 모두 수집하므로
    이 파일에 등장하는 모든 제품을 이름으로 찾을 수 있다.
    resolve_drug()의 name_to_ingredient 인자로 그대로 쓸 수 있다.
    """
    product_to_code = {}
    enc = _detect_encoding(csv_path)
    with open(csv_path, encoding=enc) as f:
        for row in csv.DictReader(f):
            pairs = ((row.get("제품명1", ""), row.get("성분코드1", "")),
                     (row.get("제품명2", ""), row.get("성분코드2", "")))
            for product, code in pairs:
                product, code = product.strip(), code.strip()
                if product and code:
                    product_to_code[product] = code
    return product_to_code


# ============================================================
# ② 약 이름 정규화  (여기서만 fuzzy. 필요하면 embedding 폴백 추가)
# ============================================================
def resolve_drug(ocr_name, name_to_ingredient, score_cutoff=80):
    """
    OCR/사진에서 나온 지저분한 이름 -> 표준 품목명 + 성분코드.
    '판단'이 아니라 '매칭'이므로 fuzzy로 충분.
    후보 신뢰도가 낮으면 None -> 사람/LLM 확인 단계로 넘김.
    """
    names = list(name_to_ingredient.keys())
    hit = process.extractOne(ocr_name, names, scorer=fuzz.WRatio,
                             score_cutoff=score_cutoff)
    if hit is None:
        return None
    matched_name, score, _ = hit
    return {"입력": ocr_name, "매칭품목": matched_name,
            "성분코드": name_to_ingredient[matched_name], "신뢰도": score}


# ============================================================
# ③ 병용금기 판정  (결정론적 = 안전 코어. 절대 LLM에 맡기지 않음)
# ============================================================
def check_interactions(ingredient_codes, partners, name_of=None):
    """
    복용 중 성분 리스트 -> 병용금기 쌍 전부 탐지.
    O(n^2)지만 n(복용 약 수)이 작아 즉시 끝남. 누락 0.
    name_of를 넘기면 코드 대신 성분명으로 보기 좋게 표시.
    """
    name_of = name_of or {}
    alerts = []
    codes = list(set(ingredient_codes))
    for a, b in combinations(codes, 2):
        for partner, reason in partners.get(a, ()):
            if partner == b:
                alerts.append({
                    "성분A": name_of.get(a, a),
                    "성분B": name_of.get(b, b),
                    "등급": "병용금기",
                    "금기사유": reason,
                    "권고": "둘 중 하나만 복용 권장 — 반드시 약사/의사 상담",
                })
    return alerts


def check_by_product_names(name1, name2, partners, name_of,
                           product_to_code, score_cutoff=60):
    """
    ★ 사용자용 메인 함수: '제품 이름' 두 개로 병용금기 판정.
    흐름:  이름 -> (rapidfuzz로) 실제 제품 찾기 -> 성분코드 -> 병용금기 판정 -> 쉬운 말 결과.

    반환 dict의 '판정' 값:
      "병용금기"          : 함께 먹으면 위험 (사유 + 약사 상담 포함)
      "금기 아님"         : 이 목록엔 없음
      "확인불가"          : 비슷한 약을 못 찾음(이름 재확인 필요)
    """
    r1 = resolve_drug(name1, product_to_code, score_cutoff)
    r2 = resolve_drug(name2, product_to_code, score_cutoff)

    # 1) 이름 매칭 실패 → 확인불가
    not_found = [orig for orig, r in ((name1, r1), (name2, r2)) if r is None]
    if not_found:
        return {
            "판정": "확인불가",
            "메시지": f"'{', '.join(not_found)}' 와(과) 비슷한 약을 찾지 못했어요. "
                      f"철자를 다시 확인해 주세요.",
        }

    # 2) 성분코드로 병용금기 판정 (결정론적 = 안전 코어)
    alerts = check_interactions([r1["성분코드"], r2["성분코드"]], partners, name_of)

    result = {
        "입력1": name1, "인식된 약1": r1["매칭품목"], "이름신뢰도1": r1["신뢰도"],
        "입력2": name2, "인식된 약2": r2["매칭품목"], "이름신뢰도2": r2["신뢰도"],
    }

    if alerts:
        a = alerts[0]
        result.update({
            "판정": "병용금기",
            "성분": f'{a["성분A"]} + {a["성분B"]}',
            "왜 위험한가": a["금기사유"] or "구체적 사유가 데이터에 기재돼 있지 않음",
            "권고": "[주의] 반드시 약사 또는 의사와 상담하세요. 임의로 함께 복용하지 마세요.",
        })
    else:
        result.update({
            "판정": "금기 아님",
            "안내": "이 두 약은 병용금기 목록에 없습니다.",
            "권고": "그래도 걱정되면 약사와 상담하세요. (이 목록에 없다고 100% 안전을 뜻하진 않아요.)",
        })
    return result


# ============================================================
# ④ LangGraph 오케스트레이션  (= 발표에서 보여줄 agent workflow)
# ------------------------------------------------------------
# 노드: 수집 -> 이름해결 -> 병용금기판정 -> (질문이면)챗봇 -> 요약
# 이 그래프 다이어그램을 PPT 18~19p에 그대로 넣으면 심층점수.
# ============================================================
from typing import TypedDict, List
try:
    from langgraph.graph import StateGraph, END
    from langchain_anthropic import ChatAnthropic
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class AgentState(TypedDict):
    raw_drugs: List[str]        # OCR/사진에서 뽑은 원본 이름들
    resolved: List[dict]        # 정규화 결과
    alerts: List[dict]          # 병용금기 경고
    user_question: str          # 챗봇 질문(있으면)
    answer: str                 # 최종 응답


def build_agent(partners, name_to_ingredient, edrug_index=None):
    """상태 그래프 조립. edrug_index는 챗봇 RAG용(③) — 없으면 챗봇 생략."""
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=1000)

    def node_resolve(state: AgentState):
        resolved = []
        for name in state["raw_drugs"]:
            r = resolve_drug(name, name_to_ingredient)
            if r:
                resolved.append(r)
        return {"resolved": resolved}

    def node_check(state: AgentState):
        codes = [r["성분코드"] for r in state["resolved"]]
        return {"alerts": check_interactions(codes, partners)}   # 결정론적

    def node_explain(state: AgentState):
        # LLM은 '판정'이 아니라 '설명'만 한다. 근거는 위 alerts에서 옴.
        alerts = state["alerts"]
        prompt = (
            "다음은 규칙엔진이 확정한 병용금기 결과다. "
            "어르신도 이해하도록 쉽게 풀어 설명하고, 반드시 약사 상담을 권하라. "
            "결과에 없는 금기를 새로 지어내지 마라.\n"
            f"{alerts}"
        )
        msg = llm.invoke(prompt)
        return {"answer": msg.content}

    def node_chatbot(state: AgentState):
        # ③ RAG: e약은요에서 관련 문서 검색 후 답변
        q = state["user_question"]
        context = ""
        if edrug_index is not None:
            context = edrug_index.search(q)   # TODO: 벡터검색 구현
        prompt = (f"참고자료:\n{context}\n\n질문: {q}\n"
                  "참고자료 범위에서만 답하고, 의료행위가 아닌 정보제공임을 밝혀라.")
        return {"answer": llm.invoke(prompt).content}

    def route(state: AgentState):
        return "chatbot" if state.get("user_question") else "explain"

    g = StateGraph(AgentState)
    g.add_node("resolve", node_resolve)
    g.add_node("check", node_check)
    g.add_node("explain", node_explain)
    g.add_node("chatbot", node_chatbot)
    g.set_entry_point("resolve")
    g.add_edge("resolve", "check")
    g.add_conditional_edges("check", route,
                            {"explain": "explain", "chatbot": "chatbot"})
    g.add_edge("explain", END)
    g.add_edge("chatbot", END)
    return g.compile()


# ============================================================
# 데모 (데이터 파일 없이 로직만 즉시 확인)
# ============================================================
if __name__ == "__main__":
    # 실제로는 load_* 로 공공데이터를 읽지만, 여기선 목업으로 흐름 검증
    partners = {
        "SIMVASTATIN": {("ITRACONAZOLE", "횡문근융해증 위험 — 병용금기")},
        "ITRACONAZOLE": {("SIMVASTATIN", "횡문근융해증 위험 — 병용금기")},
        "WARFARIN": {("ASPIRIN", "출혈 위험 증가 — 병용주의/금기")},
        "ASPIRIN": {("WARFARIN", "출혈 위험 증가 — 병용주의/금기")},
    }
    master = {
        "조코정(심바스타틴)": "SIMVASTATIN",
        "스포라녹스캡슐": "ITRACONAZOLE",
        "쿠마딘정": "WARFARIN",
        "아스피린장용정": "ASPIRIN",
    }

    # OCR가 뽑았다고 가정한 (약간 지저분한) 이름들
    ocr_drugs = ["조코정", "스포라녹스", "아스피린"]

    resolved = [resolve_drug(n, master, score_cutoff=60) for n in ocr_drugs]
    resolved = [r for r in resolved if r]
    print("정규화 결과:")
    for r in resolved:
        print("  ", r)

    codes = [r["성분코드"] for r in resolved]
    print("\n병용금기 판정:")
    for a in check_interactions(codes, partners):
        print("  ⚠️", a)
