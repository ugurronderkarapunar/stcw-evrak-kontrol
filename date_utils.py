"""
date_utils.py
-------------
Çoklu format tarih ayrıştırma ve kalan gün hesaplama işlemleri.

Vectorized pandas işlemleri kullanılarak 100.000+ satırlık dosyalarda
yüksek performans hedeflenmiştir.
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime

import pandas as pd

# Denenecek tarih formatları (öncelik sırasına göre).
# Not: pandas.to_datetime dayfirst=True ile GG.AA.YYYY / DD/MM/YYYY gibi
# Türkiye'de yaygın formatları önceliklendirir; bu liste ek bir
# "ikinci deneme" katmanı olarak kullanılır.
KNOWN_DATE_FORMATS = [
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d.%m.%y",
    "%d/%m/%y",
    "%Y.%m.%d",
    "%d %m %Y",
    "%d %B %Y",
    "%d %b %Y",
]

# Excel'in seri numarası olarak sakladığı tarihler için makul aralık.
# (1900-01-01 = 1 ... 2200-01-01 civarı ~ 110000)
_EXCEL_SERIAL_MIN = 1
_EXCEL_SERIAL_MAX = 110000


def _try_excel_serial(value) -> pd.Timestamp | None:
    """Excel seri numarası (örn. 44562) ise tarihe çevirir."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if _EXCEL_SERIAL_MIN <= f <= _EXCEL_SERIAL_MAX:
        try:
            return pd.Timestamp("1899-12-30") + pd.Timedelta(days=f)
        except (OverflowError, ValueError):
            return None
    return None


def parse_date_value(value) -> pd.Timestamp | None:
    """
    Tek bir hücre değerini olabildiğince akıllıca tarihe çevirir.
    Başarısız olursa None döner (Hatalı Tarih / Tarih Yok olarak işaretlenir).
    """
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value if not pd.isna(value) else None
    if isinstance(value, datetime):
        return pd.Timestamp(value)

    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        serial = _try_excel_serial(value)
        if serial is not None:
            return serial
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "-", "yok"}:
        return None

    # Excel seri numarası metin olarak gelmiş olabilir.
    if re.fullmatch(r"\d{4,6}(\.\d+)?", text):
        serial = _try_excel_serial(text)
        if serial is not None:
            return serial

    # ISO formatı (YYYY-MM-DD / YYYY/MM/DD) belirsizlik taşımaz; önce onu dene.
    if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}([ T].*)?", text):
        try:
            parsed = pd.to_datetime(text, dayfirst=False, errors="raise")
            if not pd.isna(parsed):
                return pd.Timestamp(parsed)
        except (ValueError, TypeError):
            pass

    # Önce pandas'ın genel ayrıştırıcısına güven (gün-öncelikli).
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(text, dayfirst=True, errors="raise")
        if not pd.isna(parsed):
            return pd.Timestamp(parsed)
    except (ValueError, TypeError):
        pass

    # Bilinen formatları tek tek dene.
    for fmt in KNOWN_DATE_FORMATS:
        try:
            return pd.Timestamp(datetime.strptime(text, fmt))
        except ValueError:
            continue

    return None


def parse_date_series(series: pd.Series) -> pd.Series:
    """
    Bir pandas Series içindeki tüm tarih değerlerini vectorized biçimde
    ayrıştırır. Karışık formatlar barındıran gerçek dünya verileri için
    tasarlanmıştır.
    """
    if series.empty:
        return series

    # Hızlı yol: pandas otomatik ayrıştırma çoğu satırı halleder.
    # Karışık formatlı (gün-öncelikli + ISO) sütunlarda pandas bilgilendirme
    # amaçlı bir uyarı üretebilir; bu beklenen bir durumdur çünkü kalan
    # satırlar zaten aşağıda satır bazlı fallback ile yeniden işlenir.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fast = pd.to_datetime(series, dayfirst=True, errors="coerce")

    # Ayrıştırılamayan satırları tek tek (satır bazlı) yeniden dene.
    mask_failed = fast.isna() & series.notna()
    if mask_failed.any():
        fast.loc[mask_failed] = series.loc[mask_failed].map(parse_date_value)

    return fast


def calculate_remaining_days(expiry_series: pd.Series, reference_date: pd.Timestamp | None = None) -> pd.Series:
    """
    Kalan Gün = Bitiş Tarihi - Bugün
    Vectorized olarak hesaplanır.
    """
    ref = reference_date or pd.Timestamp(datetime.now().date())
    delta = (expiry_series - ref).dt.days
    return delta


def is_valid_date(value: pd.Timestamp | None) -> bool:
    return value is not None and not pd.isna(value)
