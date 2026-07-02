"""
app_ui.py — 약속: 화면 디자인 시안 (기능 없음, 레이아웃/디자인만)
================================================================
· 아래쪽 탭 바 3개: 사진 올리기 / 복용 중인 약 / 병용금기 검사 결과
· 오른쪽 아래 동그란 챗봇 버튼(플로팅)
· 병원 느낌 파란 테마 / 위험=빨강 / 안전=초록 / 어르신용 큰 글씨
실행:  streamlit run app_ui.py
================================================================
"""

import streamlit as st

st.set_page_config(page_title="약속 - 복약 안전 지킴이", page_icon="💊", layout="centered")

# ============================================================
# 디자인(CSS)
# ============================================================
st.markdown("""
<style>
  :root {
    --blue: #1668c5; --blue-dark: #0d47a1; --blue-soft: #e8f1fb;
    --red: #d32f2f; --red-soft: #fdecec;
    --green: #2e7d32; --green-soft: #e9f6ea; --ink: #1c2a39;
  }
  .stApp { background: #f4f8fc; }
  html, body, [class*="css"], .stMarkdown, p, li, label { font-size: 20px !important; color: var(--ink); }

  /* Streamlit 기본 상단바/하단(검은 부분) 숨기기 */
  [data-testid="stHeader"] { background: transparent; height: 0; }
  [data-testid="stToolbar"] { display: none; }
  #MainMenu, footer { visibility: hidden; }

  /* 아래 탭 바에 안 가리도록 본문 아래 여백 확보 */
  .block-container { max-width: 640px; padding-top: 1rem; padding-bottom: 120px; }

  /* ---- 헤더 ---- */
  .header {
    background: linear-gradient(135deg, var(--blue-dark), var(--blue));
    color: #fff; border-radius: 18px; padding: 24px; text-align: center;
    margin-bottom: 18px; box-shadow: 0 6px 18px rgba(13,71,161,.25);
  }
  .header .logo { font-size: 42px; font-weight: 800; }
  .header .tagline { font-size: 20px; margin-top: 4px; color: #d6e6fb; }

  /* ================== 아래 고정 탭 바 ================== */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {
    position: fixed; bottom: 0;
    left: 50%; transform: translateX(-50%);   /* 가운데 정렬 */
    width: min(640px, 100%);                    /* 앱 폭(핸드폰)에 맞춤 */
    background: #fff; border-top: 1px solid #e0e6ec; border-radius: 16px 16px 0 0;
    box-shadow: 0 -3px 14px rgba(20,40,60,.10);
    display: flex; justify-content: space-around; gap: 0;
    padding: 6px 0; z-index: 100;
  }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    flex: 1; justify-content: center; text-align: center;
    font-size: 18px !important; font-weight: 700; padding: 10px 4px; height: auto;
  }
  [data-testid="stTabs"] [aria-selected="true"] { color: var(--blue) !important; }

  /* ---- 사진 업로드 점선 박스 ---- */
  .upload-box {
    border: 3px dashed var(--blue); background: var(--blue-soft);
    border-radius: 18px; padding: 30px 20px; text-align: center;
  }
  .upload-box .cam { font-size: 54px; }
  .upload-box .u-title { font-size: 22px; font-weight: 700; color: var(--blue-dark); margin-top: 6px; }
  .upload-box .u-sub { font-size: 18px; color: #4a6b8f; margin-top: 4px; }

  /* ---- 약 카드 ---- */
  .med-card {
    display: flex; align-items: center; justify-content: space-between;
    background: #fff; border-left: 8px solid var(--blue); border-radius: 14px;
    padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(20,40,60,.08);
  }
  .med-card .m-name { font-size: 24px; font-weight: 700; }
  .med-card .m-dose { font-size: 18px; color: #5b6b7b; margin-top: 2px; }
  .med-card .m-x {
    font-size: 22px; font-weight: 800; color: #fff; background: var(--red);
    width: 40px; height: 40px; border-radius: 50%; display: flex;
    align-items: center; justify-content: center; flex: none;
  }

  /* ---- 결과 박스 ---- */
  .result-danger { background: var(--red-soft); border: 2px solid var(--red); border-radius: 16px; padding: 22px; text-align: center; }
  .result-danger .r-icon { font-size: 44px; }
  .result-danger .r-title { font-size: 24px; font-weight: 800; color: var(--red); margin: 6px 0; }
  .result-danger .r-body { font-size: 20px; color: #7a2020; line-height: 1.6; }
  .result-safe { background: var(--green-soft); border: 2px solid var(--green); border-radius: 16px; padding: 22px; text-align: center; }
  .result-safe .r-title { font-size: 24px; font-weight: 800; color: var(--green); }

  /* ================== 오른쪽 아래 동그란 챗봇 버튼 ================== */
  [data-testid="stPopover"] {
    position: fixed !important; left: auto !important;
    right: max(16px, calc((100vw - 640px) / 2 + 16px)) !important;  /* 앱 폭 오른쪽 끝 */
    bottom: 92px !important; width: auto !important; z-index: 9999 !important;
  }
  [data-testid="stPopover"] button {
    width: 64px !important; height: 64px !important; border-radius: 50% !important;
    background: var(--blue) !important; color: #fff !important;
    font-size: 28px !important; border: none !important; padding: 0 !important;
    box-shadow: 0 6px 16px rgba(13,71,161,.45);
  }
  .bot-bubble { background: var(--blue-soft); border-radius: 16px 16px 16px 4px; padding: 14px 16px; font-size: 19px; color: var(--blue-dark); }

  .stButton>button { font-size: 20px !important; font-weight: 700; padding: 0.5em 1.1em !important; border-radius: 12px !important; }
  .stTextInput input { font-size: 20px !important; padding: 0.55em !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 헤더 (항상 위에)
# ============================================================
st.markdown("""
<div class="header">
  <div class="logo">💊 약속</div>
  <div class="tagline">복약 안전 지킴이</div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# 아래 탭 바 3개 (내용은 각 탭 안에)
# ============================================================
tab_photo, tab_meds, tab_check = st.tabs(["📷 사진", "💊 복용약", "🔍 검사결과"])

# ---- 탭 1: 약봉투 사진 올리기 ----
with tab_photo:
    st.markdown("""
    <div class="upload-box">
      <div class="cam">📷</div>
      <div class="u-title">사진 찍으면 약을 자동으로 읽어요</div>
      <div class="u-sub">아래 버튼을 눌러 약봉투/처방전 사진을 올려주세요</div>
    </div>
    """, unsafe_allow_html=True)
    photo = st.file_uploader("사진 선택", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if photo is not None:
        st.info("사진을 받았어요. (자동 인식 기능은 곧 연결됩니다 🙂)")
    st.caption("※ 지금은 화면만 있어요. 실제 자동 인식은 나중에 연결됩니다.")

# ---- 탭 2: 복용 중인 약 ----
with tab_meds:
    example_meds = [
        {"name": "클래리시드정", "dose": "250mg"},
        {"name": "브릴린타정", "dose": "90mg"},
    ]
    for m in example_meds:
        st.markdown(f"""
        <div class="med-card">
          <div>
            <div class="m-name">{m['name']}</div>
            <div class="m-dose">{m['dose']}</div>
          </div>
          <div class="m-x">✕</div>
        </div>
        """, unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    c1.text_input("약 추가", placeholder="예: 타이레놀정 500mg", label_visibility="collapsed")
    c2.button("➕ 추가")
    st.caption("※ 삭제(✕)·추가 기능은 나중에 연결됩니다.")

# ---- 탭 3: 병용금기 검사 결과 ----
with tab_check:
    st.markdown("""
    <div class="result-danger">
      <div class="r-icon">⚠️</div>
      <div class="r-title">함께 드시면 위험해요</div>
      <div class="r-body">
        <b>클래리시드 + 브릴린타</b>는 병용금기입니다.<br>
        반드시 약사·의사와 상담하세요.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("※ 안전할 때는 초록색 안심 박스가 뜹니다. (검사 기능은 나중에 연결)")


# ============================================================
# 오른쪽 아래 동그란 챗봇 버튼 (누르면 창이 열림)
# ============================================================
with st.popover("💬"):
    st.markdown('<div class="bot-bubble">안녕하세요! 약에 대해 궁금한 점을 편하게 물어보세요. 😊</div>',
                unsafe_allow_html=True)
    st.text_input("질문", placeholder="약에 대해 궁금한 걸 물어보세요", label_visibility="collapsed")
    st.caption("※ 챗봇 기능은 나중에 연결됩니다.")
