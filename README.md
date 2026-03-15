# App Review Intelligence Lab

> **학술 연구 목적 대시보드** — 무단 배포 금지
> Academic Research Dashboard — Unauthorized distribution is prohibited.

---

## 프로젝트 개요

**App Review Intelligence Lab**은 모바일 앱 리뷰 데이터를 기반으로 사용자 경험을 정량 분석하고, 경쟁 앱 간 기능별 차이를 통계적으로 비교하는 웹 대시보드입니다.

Google Play Store 및 Apple App Store에서 리뷰를 실시간 수집하고, 한국어 형태소 분석 및 로지스틱 회귀 기반 오즈비(OR) 분석을 통해 **기능 개선 우선순위**를 도출합니다.

---

## 연구 배경 및 목적

모바일 앱 시장에서 사용자 리뷰는 제품 품질과 사용자 만족도를 반영하는 핵심 데이터입니다. 기존 연구들은 리뷰의 감성 분류(긍정/부정)에 집중했으나, **기능 단위의 경쟁 우위 분석**과 **개선 우선순위 도출**에 대한 체계적 방법론은 부족한 상황입니다.

본 연구는 다음을 목적으로 합니다:

1. **리뷰 기반 기능 인식 분석** — 사용자가 언급하는 기능 카테고리를 자동 분류
2. **오즈비(OR) 기반 긍정/부정 연관성 측정** — 각 기능이 긍·부정 리뷰와 얼마나 연관되는지 통계적으로 정량화
3. **ΔOR 경쟁 비교** — 기준 앱 대비 경쟁 앱의 기능별 우위/열위 측정
4. **우선순위 매트릭스 도출** — 개선 효과가 가장 큰 기능 영역을 식별하여 제품 로드맵 수립 지원

---

## 현재 개발 상태

| 항목 | 내용 |
|------|------|
| 버전 | **v1.0** (개발 진행 중) |
| 상태 | 논문 작성과 병행 개발 중 |
| 플랫폼 지원 | Google Play Store ✅ / Apple App Store ✅ |
| 분석 앱 수 | 최대 5개 동시 비교 |

> 본 대시보드는 학위 논문 연구를 위해 개발 중이며, 논문 및 연구 결과가 공식 발표되기 전까지 **임의 배포 및 상업적 이용을 금지합니다**.

---

## 주요 기능

- **리뷰 실시간 수집** — Google Play / App Store 동시 수집, Android·iOS 통합 분석
- **한국어 NLP** — kiwipiepy 형태소 분석, 불용어 제거, TF 기반 키워드 추출
- **4종 워드클라우드** — 전체 / 긍정 / 보통 / 부정 리뷰 키워드 시각화
- **OR 분석** — 로지스틱 회귀 기반 기능별 오즈비 및 신뢰구간 계산
- **ΔOR 경쟁 분석** — 기준 앱 대비 경쟁 앱의 기능별 우위/열위 정량화
- **우선순위 매트릭스** — ΔOR × 취약도 결합 점수로 개선 우선순위 도출
- **통계 검증** — Pseudo R², VIF, 민감도 분석, 기간 안정성 검증

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | Streamlit |
| 데이터 수집 | google-play-scraper, iTunes RSS API |
| NLP | kiwipiepy, soynlp |
| 통계 분석 | statsmodels, scikit-learn, scipy |
| 시각화 | Plotly, Matplotlib, WordCloud |

---

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 앱 실행
streamlit run app.py
```

---

## 문의

- https://app-review-analytics.streamlit.app/
- **연구자**: Loki Moon
- **이메일**: wata0414@gmail.com
- 논문 발표 전 무단 배포 금지
