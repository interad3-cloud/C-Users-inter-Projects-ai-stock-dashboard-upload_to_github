"""앱 전역 설정 및 상수."""

PERIOD_OPTIONS = {
    "최근 1년": "1y",
    "최근 3년": "3y",
    "최근 5년": "5y",
}

CHART_PERIOD_OPTIONS = {
    "1일": "1d",
    "5일": "5d",
    "1개월": "1mo",
    "1년": "1y",
    "전체": "max",
}

# yfinance 재무제표 행 이름 → 한국어 지표명 (fallback 순서대로 탐색)
FINANCIAL_ROW_KEYS = {
    "revenue": ["Total Revenue", "Revenue", "Operating Revenue"],
    "operating_income": ["Operating Income", "EBIT"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "operating_cashflow": [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
    ],
    "total_liabilities": [
        "Total Liabilities Net Minority Interest",
        "Total Liab",
        "Total Liabilities",
    ],
    "stockholders_equity": [
        "Stockholders Equity",
        "Total Stockholder Equity",
        "Common Stock Equity",
        "Total Equity Gross Minority Interest",
    ],
}

METRIC_LABELS_KO = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "operating_cashflow": "영업현금흐름",
    "debt_ratio": "부채비율",
    "roe": "ROE(%)",
}

MA_WINDOWS = (20, 60, 120)
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2.0

# 재무 추정 모델 파라미터
FORECAST_YEARS = 3
REVENUE_GROWTH_WEIGHT_CAGR = 0.4
REVENUE_GROWTH_WEIGHT_YOY = 0.6
CORPORATE_TAX_RATE = 0.20
MARGIN_IMPROVEMENT_Y2 = 0.005
MARGIN_IMPROVEMENT_Y3 = 0.010
DEFAULT_TARGET_PER = 10.0

# 사이클 업종 분류
CYCLICAL_SECTORS = {
    "Technology",
    "Industrials",
    "Basic Materials",
    "Energy",
    "Consumer Cyclical",
}
CYCLICAL_INDUSTRIES = {
    "Semiconductors",
    "Semiconductor Equipment & Materials",
    "Auto Manufacturers",
    "Auto Parts",
    "Chemicals",
    "Specialty Chemicals",
    "Steel",
    "Memory",
}
CYCLICAL_KEYWORDS = (
    "semiconductor",
    "반도체",
    "auto",
    "자동차",
    "chemical",
    "화학",
    "steel",
    "철강",
    "memory",
    "디스플레이",
)
EXPORT_FOCUSED_KEYWORDS = (
    "packaged foods",
    "food",
    "beverage",
    "consumer",
    "음식",
    "식품",
    "라면",
    "noodle",
)

# 시나리오 파라미터
MARGIN_TREND_WEIGHT_CYCLICAL = 1.2
SCENARIO_BULL_GROWTH_FACTOR = 1.30
SCENARIO_BULL_PER_FACTOR = 1.10
SCENARIO_BEAR_GROWTH_FACTOR = 0.50
SCENARIO_BEAR_PER_FACTOR = 0.90
FX_WEAK_BENEFIT_EXPORT = 0.8
FX_WEAK_PENALTY_DOMESTIC = -0.3

DISCLAIMER_KO = (
    "본 자료는 투자 참고용 정보제공 목적으로 작성되었으며, "
    "yfinance 공개 데이터 및 리서치센터 내부 추정 모델을 기반으로 함. "
    "정확성·완전성·실시간성을 보장하지 않으며, 투자 결정은 투자자 본인의 "
    "판단과 책임 하에 이루어져야 함."
)
