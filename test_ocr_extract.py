"""
test_ocr_extract.py — 사진 -> 약 이름 추출(OCR) 단독 테스트
실행: python test_ocr_extract.py
"""
from PIL import Image, ImageDraw, ImageFont
import io
import pharma_chatbot as pc

# 1) 테스트용 처방전 이미지 만들기
FONT = "C:/Windows/Fonts/malgun.ttf"
img = Image.new("RGB", (720, 400), "white")
d = ImageDraw.Draw(img)
d.text((30, 25), "처 방 전", fill="black", font=ImageFont.truetype(FONT, 34))
d.text((30, 90), "의료기관: 순천향대학교 구미병원", fill="black", font=ImageFont.truetype(FONT, 20))
meds = ["1. 클래리시드정250mg   1일 2회", "2. 브릴린타정90mg      1일 2회",
        "3. 타이레놀정500mg     1일 3회"]
y = 150
for m in meds:
    d.text((45, y), m, fill="black", font=ImageFont.truetype(FONT, 22)); y += 45
buf = io.BytesIO(); img.save(buf, format="PNG")

# 2) OCR 함수로 약 이름 뽑기
print("\n사진에서 약 이름 추출 중...")
names = pc.extract_drugs_from_image(buf.getvalue(), "image/png")
print("추출된 약 이름:")
for n in names:
    print("  -", n)
print(f"\n총 {len(names)}개 인식")
