"""
build_data.py — 152MB CSV를 배포용 작은 JSON으로 변환 (로컬에서 1회 실행)
실행: python build_data.py
결과: dur_data.json  (이 파일을 깃허브에 올려 Railway에서 사용)
"""
import json
from dur_agent_starter import load_contraindications, load_product_index

CSV = "한국의약품안전관리원_병용금기약물_20240625.csv"

print("CSV 읽는 중... (조금 걸려요)")
partners, name_of = load_contraindications(CSV)   # {코드: {(상대코드, 사유)}}
product_to_code = load_product_index(CSV)          # {제품명: 성분코드}

# set/tuple 은 JSON 저장이 안 되므로 list 로 변환
partners_json = {code: [[p, r] for (p, r) in pairs] for code, pairs in partners.items()}

data = {
    "partners": partners_json,
    "name_of": name_of,
    "product_to_code": product_to_code,
}
with open("dur_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

print(f"[완료] dur_data.json 저장 "
      f"(성분 {len(partners):,} · 제품 {len(product_to_code):,})")
