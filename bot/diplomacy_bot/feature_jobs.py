"""Feature job kaydı — feature_scheduler köprüsü."""

from __future__ import annotations

from telegram.ext import Application

from .feature_scheduler import register_all_feature_jobs


def register_feature_jobs(app: Application) -> None:
    register_all_feature_jobs(app)
