# 주식 분석 대시보드

Streamlit 기반 주식 분석 웹 앱입니다. 티커를 입력하면 **주가·기술적 차트**, **재무제표**, **전통적 재무 추정(3개년)** 및 **목표주가**를 한국어로 제공합니다.

## 기능

- **탭 1 — 차트 분석**: 캔들스틱, MA(20/60/120), 거래량, RSI, MACD
- **탭 2 — 재무제표**: 손익·재무상태·현금흐름 기반 주요 지표
- **탭 3 — 실적 전망**: 증권사 스타일 재무 추정 모델 (CAGR·이익률·Target PER·BUY/HOLD/SELL)
- **탭 4 — 증권사 리포트**: LS증권 형식 2단 UI + PDF (업종·컨센서스·시나리오)

## 고도화 분석 (`analyst.py`)

1. **업종 사이클 분기** — Technology/Semiconductor 등 사이클 업종은 OPM 추세 1.2x + PER High-Low Average
2. **컨센서스 비교** — `earnings_estimates` 기반 어닝 서프라이즈 판별
3. **비용 구조** — COGS%/SG&A% 3개년 추이 및 정성 드라이버
4. **거시 민감도** — 환율 시나리오, 해외/내수 비중 추정
5. **Bull/Base/Bear** — 3가지 시나리오 목표주가

## 추정 모델 (`forecasting.py`)

- **매출**: 3개년 CAGR(40%) + 직전년 YoY(60%) 가중 성장률
- **영업이익**: 3개년 평균 이익률, Y+2 +0.5%p, Y+3 +1.0%p 개선
- **순이익**: 영업이익 × (1 − 20% 법인세)
- **목표주가**: 예상 EPS × Target PER (현재·3개년 평균 PER 혼합)
- **정성 코멘트**: 규칙 기반 If-Else 템플릿 (LLM 미사용)

## 설치 및 실행

```bash
git clone <your-repo-url>
cd ai-stock-dashboard
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

## Streamlit Cloud 배포

1. GitHub 저장소에 프로젝트 푸시
2. [share.streamlit.io](https://share.streamlit.io) → **New app**
3. **Main file path**: `app.py`
4. **Requirements file**: `requirements.txt` (기본값)
5. (선택) PDF 한글 폰트: `packages.txt`에 `fonts-nanum` 포함됨 — Cloud에서 Nanum Gothic 자동 설치

로컬·클라우드 모두 **저장소 루트**를 작업 디렉터리로 사용하며, 코드는 `paths.py`의 `PROJECT_ROOT` / `asset_path()`로 상대 경로를 해석합니다.

### 모바일에서 접속 (같은 Wi‑Fi)

`localhost`는 **각 기기 자신**을 가리킵니다. PC에서 돌아가는 앱을 폰에서 보려면 PC의 **내부 IP**로 접속해야 합니다.

1. PC와 휴대폰을 **같은 Wi‑Fi**에 연결
2. PC에서 Streamlit 실행 (`.streamlit/config.toml`에 `address = "0.0.0.0"` 설정됨)
3. PC IP 확인: PowerShell에서 `ipconfig` → `IPv4 Address` (예: `172.30.1.35`)
4. 휴대폰 브라우저에서 **`http://172.30.1.35:8501`** 입력  
   (`#eb1a4672` 같은 해시는 붙이지 않아도 됩니다)

접속이 안 되면 Windows 방화벽에서 **8501 포트 허용** (관리자 PowerShell):

```powershell
New-NetFirewallRule -DisplayName "Streamlit 8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
```

**LTE/5G만 쓰는 휴대폰**이나 **외부에서** 접속하려면 ngrok·Cloudflare Tunnel 등 터널링 또는 클라우드 배포가 필요합니다.

## 프로젝트 구조

```
app.py              # Streamlit UI
paths.py            # 프로젝트 루트·assets 상대 경로
forecasting.py      # 재무 추정·목표주가·정성 코멘트
analyst.py          # 5대 고도화 금융 로직
research_report.py  # LS증권 형식 리포트 HTML
report_pdf.py       # PDF 생성 (reportlab)
config.py           # 모델 파라미터
data_loader.py    # yfinance + 캐싱
indicators.py     # RSI, MACD, MA
charts.py         # Plotly 차트
financials.py     # 재무 지표 가공
```

## 면책

본 앱의 데이터(yfinance) 및 추정 결과는 **투자 참고용**이며, 투자 손실에 대한 책임은 사용자에게 있습니다.
