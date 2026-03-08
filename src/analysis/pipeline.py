"""
전체 분석 파이프라인 오케스트레이터

단계:
1. 리뷰 데이터 로드 (수집 완료 후 DataFrame)
2. 텍스트 정규화
3. 형태소 분석
4. 불용어 제거
5. 기능 카테고리 더미 변수 생성
6. 회귀 분석 (앱별)
7. ΔOR 계산
8. 중간 산출물 저장

progress_callback(step: int, total: int, message: str) 형태로 진행 보고.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import DATA_PROCESSED_DIR, UPDATE_FLAG_DAYS
from src.preprocess.normalizer import normalize_series
from src.preprocess.tokenizer import tokenize_series
from src.preprocess.stopwords import remove_stopwords_batch
from src.analysis.keyword import build_freq_table, build_tfidf_keywords, map_feature_categories, get_category_columns
from src.analysis.model import build_regression_df, run_logistic_regression
from src.analysis.delta_or import compute_delta_or


TOTAL_STEPS = 7


def _cb(callback, step: int, msg: str):
    if callback:
        callback(step, TOTAL_STEPS, msg)


def run_pipeline(
    raw_df: pd.DataFrame,
    progress_callback=None,
) -> dict:
    """
    raw_df: 수집된 리뷰 DataFrame (ReviewRecord 스키마)
    반환: {
        "processed_df": DataFrame,
        "freq_table": DataFrame,
        "tfidf_table": DataFrame,
        "or_results": {app_name: DataFrame},
        "combined_or": DataFrame,
        "errors": [str]
    }
    """
    output = {
        "processed_df": pd.DataFrame(),
        "freq_table": pd.DataFrame(),
        "tfidf_table": pd.DataFrame(),
        "or_results": {},
        "combined_or": pd.DataFrame(),
        "errors": [],
    }

    if raw_df.empty:
        output["errors"].append("수집된 리뷰 데이터가 없습니다.")
        return output

    df = raw_df.copy()

    # ── Step 1: 텍스트 정규화 ─────────────────────────────────────────────────
    _cb(progress_callback, 1, "텍스트를 정규화하고 있어요...")
    try:
        df["content_clean"] = normalize_series(df["content"].fillna("").tolist())
    except Exception as e:
        output["errors"].append(f"정규화 실패: {e}")
        return output

    # ── Step 2: 형태소 분석 ───────────────────────────────────────────────────
    _cb(progress_callback, 2, "형태소를 분석하고 있어요...")
    try:
        tokens_raw = tokenize_series(df["content_clean"].tolist())
    except Exception as e:
        output["errors"].append(f"형태소 분석 실패: {e}")
        return output

    # ── Step 3: 불용어 제거 ───────────────────────────────────────────────────
    _cb(progress_callback, 3, "불용어를 제거하고 있어요...")
    try:
        tokens_clean = remove_stopwords_batch(tokens_raw)
        df["tokens"] = tokens_clean
    except Exception as e:
        output["errors"].append(f"불용어 제거 실패: {e}")
        return output

    # ── Step 4: 빈도 분석 & TF-IDF ───────────────────────────────────────────
    _cb(progress_callback, 4, "키워드를 추출하고 있어요...")
    try:
        freq_table  = build_freq_table(tokens_clean)
        tfidf_table = build_tfidf_keywords(tokens_clean)
        output["freq_table"]  = freq_table
        output["tfidf_table"] = tfidf_table
    except Exception as e:
        output["errors"].append(f"키워드 추출 실패: {e}")

    # ── Step 5: 기능 카테고리 더미 ────────────────────────────────────────────
    _cb(progress_callback, 5, "기능 카테고리를 매핑하고 있어요...")
    try:
        dummy_df = map_feature_categories(tokens_clean)
        dummy_df.index = df.index
        df = pd.concat([df, dummy_df], axis=1)
    except Exception as e:
        output["errors"].append(f"기능 매핑 실패: {e}")
        return output

    # update_flag 생성
    try:
        _add_update_flag(df)
    except Exception:
        df["update_flag"] = 0

    output["processed_df"] = df

    # 중간 저장
    try:
        _save_processed(df)
    except Exception:
        pass

    # ── Step 6: 로지스틱 회귀 (앱별) ─────────────────────────────────────────
    _cb(progress_callback, 6, "로지스틱 회귀를 수행하고 있어요...")
    feature_cols = get_category_columns(df)
    or_results: dict[str, pd.DataFrame] = {}

    for app_name, app_df in df.groupby("app_name"):
        reg_df = build_regression_df(app_df)
        if len(reg_df) < 30:
            output["errors"].append(f"[{app_name}] 데이터가 부족하여 회귀 분석을 건너뜁니다.")
            continue
        try:
            or_df = run_logistic_regression(reg_df, feature_cols)
            if not or_df.empty:
                or_results[str(app_name)] = or_df
        except Exception as e:
            output["errors"].append(f"[{app_name}] 회귀 분석 실패: {e}")

    output["or_results"] = or_results

    # ── Step 7: ΔOR 계산 ──────────────────────────────────────────────────────
    _cb(progress_callback, 7, "ΔOR 및 우선순위 점수를 계산하고 있어요...")
    if len(or_results) >= 2:
        try:
            base_app = list(or_results.keys())[0]
            combined = compute_delta_or(or_results, base_app)
            output["combined_or"] = combined
        except Exception as e:
            output["errors"].append(f"ΔOR 계산 실패: {e}")
    elif len(or_results) == 1:
        # 앱이 1개면 ΔOR 없이 OR만 반환
        app_name = list(or_results.keys())[0]
        df_or = or_results[app_name].copy()
        df_or["delta_or"] = None
        df_or["priority_score"] = None
        df_or["app_name"] = app_name
        output["combined_or"] = df_or

    return output


def _add_update_flag(df: pd.DataFrame) -> None:
    """reviewCreatedVersion 기반 update_flag 생성"""
    if "review_created_version" not in df.columns:
        df["update_flag"] = 0
        return

    df["review_date_dt"] = pd.to_datetime(df["review_date"], errors="coerce")
    df["update_flag"] = 0

    for app_name, group in df.groupby("app_name"):
        versions = group["review_created_version"].dropna()
        version_changes = versions[versions != versions.shift()]
        for idx in version_changes.index:
            change_date = df.loc[idx, "review_date_dt"]
            if pd.isna(change_date):
                continue
            mask = (
                (df["app_name"] == app_name) &
                (df["review_date_dt"] >= change_date) &
                (df["review_date_dt"] <= change_date + pd.Timedelta(days=UPDATE_FLAG_DAYS))
            )
            df.loc[mask, "update_flag"] = 1


def _save_processed(df: pd.DataFrame) -> None:
    """전처리 결과 저장"""
    save_df = df.copy()
    # tokens 컬럼은 join해서 저장
    if "tokens" in save_df.columns:
        save_df["tokens"] = save_df["tokens"].apply(lambda x: " ".join(x) if isinstance(x, list) else "")

    app_ids = df["app_id"].unique() if "app_id" in df.columns else ["unknown"]
    app_str = "_".join(str(a) for a in app_ids[:2])
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d")
    path = DATA_PROCESSED_DIR / f"processed_{app_str}_{ts}.csv"
    save_df.to_csv(path, index=False, encoding="utf-8-sig")
