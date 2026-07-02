"""
test_dur.py — 병용금기 데이터 로드 & 경고 테스트 (초보자용)
실행:  python test_dur.py
"""

from dur_agent_starter import load_contraindications, check_interactions

CSV = "한국의약품안전관리원_병용금기약물_20240625.csv"

# ── 2번: CSV 불러오기 + 로드된 금기 성분 개수 출력 ───────────────
print("CSV 불러오는 중... (파일이 커서 몇 초 걸릴 수 있어요)")
partners, name_of = load_contraindications(CSV)

print(f"\n[로드 완료]")
print(f"  병용금기 성분 종류(코드 개수): {len(partners):,} 개")
print(f"  성분명이 매핑된 성분 개수    : {len(name_of):,} 개")

# ── 3번: 실제 금기인 성분 두 개를 뽑아 check_interactions 테스트 ──
# partners 에서 진짜 금기 쌍 하나를 자동으로 꺼낸다.
code_a = next(iter(partners))                 # 아무 성분코드 하나
code_b, reason = next(iter(partners[code_a])) # 그 성분과 금기인 상대 하나

print(f"\n[테스트에 쓸 실제 금기 쌍]")
print(f"  성분A: {name_of.get(code_a, code_a)}  (코드 {code_a})")
print(f"  성분B: {name_of.get(code_b, code_b)}  (코드 {code_b})")

alerts = check_interactions([code_a, code_b], partners, name_of)

print(f"\n[경고 결과] {len(alerts)} 건")
for a in alerts:
    print("  [경고]", a["성분A"], "+", a["성분B"], "->", a["등급"])
    print("     사유:", a["금기사유"] or "(사유 없음)")
    print("     권고:", a["권고"])

# ── 참고: 금기가 아닌 조합은 경고가 0건이어야 정상 ──────────────
none_alerts = check_interactions([code_a, "존재하지않는코드XYZ"], partners, name_of)
print(f"\n[대조군] 금기 아닌 조합 경고 건수: {len(none_alerts)} 건  (0이면 정상)")
