# Railway 배포 가이드 (약속)

초보자용 단계별 안내입니다. 이 저장소를 Railway에 올려 인터넷에서 접속 가능한 앱으로 만듭니다.

## 준비된 것 (이미 됨)
- `requirements.txt` — 필요한 패키지 목록 (Railway가 자동 설치)
- `Procfile` — 앱 실행 명령 (`streamlit run app.py ...`)
- `.python-version` — 파이썬 버전(3.12)
- `dur_data.json` — 152MB CSV를 3.7MB로 압축한 데이터 (CSV 대신 사용)

> 참고: 실행 대상은 **`app.py`**(기능이 연결된 챗봇)입니다.

## 배포 단계

### 1. 깃허브에 최신 코드 올리기
이 준비물들이 커밋·푸시되어 있어야 합니다. (아래 "커밋/푸시"는 이미 완료)

### 2. Railway 프로젝트 만들기
1. https://railway.app 가입 (깃허브 계정으로 로그인 추천)
2. **New Project** → **Deploy from GitHub repo** 선택
3. 저장소 **`gyuwonlee05/agent`** 선택
4. Railway가 자동으로 `requirements.txt` 설치 후 `Procfile` 명령으로 실행합니다.

### 3. API 키 넣기 (제일 중요!)
`.env`는 깃허브에 안 올라가므로, Railway에 직접 넣어야 합니다.
1. 프로젝트 → **Variables** 탭
2. 새 변수 추가:
   - 이름: `ANTHROPIC_API_KEY`
   - 값: 본인의 Anthropic 키 (`sk-ant-...`)
3. (음성 기능을 붙였다면) `OPENAI_API_KEY` 도 같은 방식으로 추가
4. 저장하면 자동으로 재배포됩니다.

### 4. 공개 주소 만들기
1. 프로젝트 → **Settings** → **Networking**
2. **Generate Domain** 클릭 → `xxxx.up.railway.app` 주소 생성
3. 그 주소로 접속하면 앱이 열립니다.

## 문제가 생기면
- **앱이 안 켜짐**: Railway의 **Deployments → Logs** 에서 에러 확인
- **"API 키" 에러**: Variables 에 `ANTHROPIC_API_KEY` 가 제대로 들어갔는지 확인
- **파이썬 버전 문제**: Variables 에 `NIXPACKS_PYTHON_VERSION = 3.12` 추가

## 비용
- Railway는 무료 체험 크레딧 제공(이후 사용량 기반 과금)
- Anthropic/OpenAI API는 사용한 만큼 별도 과금
