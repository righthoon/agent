"""
app.py — 약손: 복약안전 웹 화면 (Streamlit 시연용)
================================================================
화면(UI)만 담당하고, 챗봇/판정 로직은 chatbot_core 부품을 갖다 쓴다.
실행:  streamlit run app.py
================================================================
"""

import streamlit as st
import chatbot_core as cc      # 화면과 분리된 챗봇/판정 '부품'

# ── 페이지 기본 설정 ───────────────────────────────
st.set_page_config(page_title="약손 - 복약안전 도우미", page_icon="💊", layout="centered")

# ── 어르신용 큰 글씨 + 색 구분 스타일 ───────────────
st.markdown("""
<style>
  html, body, [class*="css"], .stMarkdown, p, li, label { font-size: 20px !important; }
  h1 { font-size: 40px !important; }
  h2 { font-size: 30px !important; }
  .stButton>button { font-size: 22px !important; padding: 0.5em 1em !important; font-weight: 700; }
  .med { font-size: 24px; font-weight: 700; padding: 8px 6px; }
  .stTextInput input { font-size: 22px !important; padding: 0.5em !important; }
  div[data-testid="stChatInput"] textarea { font-size: 20px !important; }
</style>
""", unsafe_allow_html=True)

st.title("💊 약손 — 복약안전 도우미")
st.caption("이 서비스는 의료행위가 아니라 정보 제공입니다. 정확한 판단은 약사·의사와 상담하세요.")

# ── 세션 상태(화면을 새로 그려도 유지되는 기억) ──────
if "meds" not in st.session_state:
    st.session_state.meds = []        # 복용 중인 약 목록
if "chat" not in st.session_state:
    st.session_state.chat = []        # 대화 기록 [{"role","content"}]


# ============================================================
# 📷 약봉투/처방전 사진으로 자동 입력 (OCR · Claude 비전)
# ============================================================
st.header("📷 사진으로 약 자동 입력")

uploaded = st.file_uploader("약봉투 또는 처방전 사진을 올리세요 (jpg / png)",
                            type=["jpg", "jpeg", "png"])
if uploaded is not None:
    file_id = f"{uploaded.name}-{uploaded.size}"
    if st.session_state.get("last_ocr_file") != file_id:      # 같은 사진 중복 처리 방지
        with st.spinner("사진에서 약 이름을 읽는 중... (Claude 비전)"):
            found = cc.extract_drugs_from_image(uploaded.getvalue(),
                                                uploaded.type or "image/jpeg")
        added = []
        for n in found:
            n = str(n).strip()
            if n and n not in st.session_state.meds:
                st.session_state.meds.append(n)               # 목록에 자동 추가
                added.append(n)
        st.session_state.last_ocr_file = file_id
        if added:
            st.success("사진에서 약을 찾아 목록에 넣었어요: " + ", ".join(added))
        else:
            st.warning("사진에서 약 이름을 찾지 못했어요. 아래에서 손으로 추가해 주세요.")
    st.image(uploaded, caption="업로드한 사진", width=300)


# ============================================================
# ① 복용 중인 약 입력
# ============================================================
st.header("① 복용 중인 약")

with st.form("add_med", clear_on_submit=True):
    c1, c2 = st.columns([4, 1])
    name = c1.text_input("약 이름", label_visibility="collapsed",
                         placeholder="예: 클래리시드정")
    added = c2.form_submit_button("➕ 추가")
    if added and name.strip():
        st.session_state.meds.append(name.strip())

if st.session_state.meds:
    for i, m in enumerate(st.session_state.meds):
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"<div class='med'>💊 {m}</div>", unsafe_allow_html=True)
        if c2.button("삭제", key=f"del{i}"):
            st.session_state.meds.pop(i)
            st.rerun()
    if st.button("🗑 목록 비우기"):
        st.session_state.meds = []
        st.rerun()
else:
    st.info("아직 추가된 약이 없어요. 위 칸에 약 이름을 넣고 '추가'를 눌러주세요.")


# ============================================================
# ② 병용금기 검사 (자동)
# ============================================================
st.header("② 같이 먹어도 되는지 검사")
st.caption("약이 2개 이상이면 버튼 없이 자동으로 검사합니다.")

if len(st.session_state.meds) < 2:
    st.info("약을 2개 이상 넣으면 여기서 자동으로 검사해요.")
else:
    res = cc.check_meds(st.session_state.meds)                # ★ 부품의 판정 함수
    if res.get("병용금기_건수", 0) > 0:
        for a in res["병용금기_목록"]:
            st.error(
                f"### ⚠️ 위험: 함께 드시면 안 됩니다\n"
                f"**{a['성분A']} + {a['성분B']}**\n\n"
                f"이유: {a['이유']}\n\n"
                f"👉 임의로 복용하지 마시고, **반드시 약사·의사와 상담**하세요."
            )
    else:
        st.success(
            "### ✅ 안심하셔도 좋아요\n"
            "입력하신 약들은 병용금기 목록에 없습니다.\n\n"
            "그래도 정확한 판단은 약사·의사와 상담하세요."
        )
    if res.get("데이터에서_못찾은_약"):
        st.info("참고: 다음 약은 데이터에서 찾지 못해 검사에서 빠졌어요 → "
                + ", ".join(res["데이터에서_못찾은_약"])
                + ". 이 약들은 약사님께 직접 확인해 주세요.")


# ============================================================
# ③ AI 챗봇 상담  (부품 get_chatbot_response 그대로 사용)
# ============================================================
st.header("③ AI 챗봇에게 물어보기")
st.caption("예: '내 약들 같이 먹어도 돼?', '와파린이랑 조심할 음식은?', '타이레놀 부작용은?'")

for turn in st.session_state.chat:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

q = st.chat_input("약에 대해 궁금한 점을 입력하세요")
if q:
    st.session_state.chat.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("약손이 확인하는 중..."):
            answer = cc.get_chatbot_response(st.session_state.chat, st.session_state.meds)
        st.markdown(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer})
