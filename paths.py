"""프로젝트 루트 및 상대 경로 유틸리티."""

from __future__ import annotations

from pathlib import Path

# app.py와 동일 레벨 = Streamlit Cloud 저장소 루트
PROJECT_ROOT = Path(__file__).resolve().parent


def asset_path(*parts: str) -> Path:
    """`assets/` 하위 파일 경로 (예: asset_path('fonts', 'NanumGothic.ttf'))."""
    return PROJECT_ROOT.joinpath("assets", *parts)


def resolve_from_root(*parts: str) -> Path:
    """프로젝트 루트 기준 임의 경로."""
    return PROJECT_ROOT.joinpath(*parts)
