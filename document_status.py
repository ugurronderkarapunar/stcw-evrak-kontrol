"""
document_status.py
-------------------
Belge durumu sınıflandırma mantığı ve sabitleri.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

STATUS_EXPIRED = "Süresi Geçmiş"
STATUS_CRITICAL = "Kritik"
STATUS_UPCOMING = "Yaklaşıyor"
STATUS_VALID = "Geçerli"
STATUS_MISSING = "Tarih Yok"

STATUS_ORDER = [STATUS_EXPIRED, STATUS_CRITICAL, STATUS_UPCOMING, STATUS_VALID, STATUS_MISSING]

STATUS_COLORS = {
    STATUS_EXPIRED: "#E53935",   # kırmızı
    STATUS_CRITICAL: "#FB8C00",  # turuncu
    STATUS_UPCOMING: "#FDD835",  # sarı
    STATUS_VALID: "#43A047",     # yeşil
    STATUS_MISSING: "#9E9E9E",   # gri
}

STATUS_ICONS = {
    STATUS_EXPIRED: "🔴",
    STATUS_CRITICAL: "🟠",
    STATUS_UPCOMING: "🟡",
    STATUS_VALID: "🟢",
    STATUS_MISSING: "⚪",
}


@dataclass(frozen=True)
class StatusThresholds:
    critical_days: int = 30
    upcoming_days: int = 90


def classify_status(remaining_days: pd.Series, thresholds: StatusThresholds = StatusThresholds()) -> pd.Series:
    """
    Kalan güne göre vectorized durum sınıflandırması yapar.
    NaN (tarih yok/hatalı) -> Tarih Yok
    < 0 -> Süresi Geçmiş
    0-30 -> Kritik
    31-90 -> Yaklaşıyor
    90+ -> Geçerli
    """
    conditions = [
        remaining_days.isna(),
        remaining_days < 0,
        (remaining_days >= 0) & (remaining_days <= thresholds.critical_days),
        (remaining_days > thresholds.critical_days) & (remaining_days <= thresholds.upcoming_days),
        remaining_days > thresholds.upcoming_days,
    ]
    choices = [STATUS_MISSING, STATUS_EXPIRED, STATUS_CRITICAL, STATUS_UPCOMING, STATUS_VALID]
    return pd.Series(np.select(conditions, choices, default=STATUS_MISSING), index=remaining_days.index)
