"""
data_processor.py
------------------
Uygulamanın çekirdek iş mantığı.

Sorumluluklar:
- Ham DataFrame'i standart şemaya dönüştürme
- Tarih ayrıştırma ve kalan gün hesaplama
- Belge durumu sınıflandırma
- Personel bazında birleştirme (aynı kişi birden fazla satırda olabilir)
- Eksik / hatalı veri tespiti

Tüm işlemler vectorized olacak şekilde tasarlanmıştır; 100.000+ satırlık
dosyalarda döngüsüz (loop-free) çalışma hedeflenir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from models.document_status import (
    STATUS_MISSING,
    StatusThresholds,
    classify_status,
)
from utils.column_mapper import (
    FIELD_BELGE_ADI,
    FIELD_BITIS_TARIHI,
    FIELD_PERSONEL_ADI,
    FIELD_UNVAN,
    ColumnMapping,
    apply_mapping,
)
from utils.date_utils import calculate_remaining_days, parse_date_series

# İşlenmiş veri setindeki ek/türetilmiş kolon adları
COL_KALAN_GUN = "kalan_gun"
COL_DURUM = "durum"
COL_TARIH_HATALI = "tarih_hatali"
COL_BELGE_EKSIK = "belge_eksik"


@dataclass
class ProcessingSummary:
    total_employees: int = 0
    total_titles: int = 0
    total_documents: int = 0
    expired_count: int = 0
    critical_count: int = 0
    upcoming_count: int = 0
    missing_document_count: int = 0
    missing_date_count: int = 0
    invalid_date_count: int = 0


@dataclass
class ProcessedData:
    detail_df: pd.DataFrame  # her satır bir belge kaydı
    employee_df: pd.DataFrame  # her satır bir personel (birleştirilmiş)
    summary: ProcessingSummary = field(default_factory=ProcessingSummary)


def process_dataframe(
    raw_df: pd.DataFrame,
    mapping: ColumnMapping,
    thresholds: StatusThresholds | None = None,
) -> ProcessedData:
    """
    Ham veriyi alır, standart şemaya çevirir ve tüm türetilmiş
    alanları (kalan gün, durum, eksik/hatalı bayrakları) hesaplar.
    """
    thresholds = thresholds or StatusThresholds()

    df = apply_mapping(raw_df, mapping.mapping)

    # Metin alanlarını temizle
    for col in (FIELD_PERSONEL_ADI, FIELD_UNVAN, FIELD_BELGE_ADI):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    df[FIELD_PERSONEL_ADI] = df[FIELD_PERSONEL_ADI].replace("", pd.NA)
    if FIELD_UNVAN in df.columns:
        df[FIELD_UNVAN] = df[FIELD_UNVAN].replace("", pd.NA).fillna("Belirtilmemiş")
    else:
        df[FIELD_UNVAN] = "Belirtilmemiş"

    df[FIELD_BELGE_ADI] = df[FIELD_BELGE_ADI].replace("", pd.NA)

    # Personel adı olmayan satırları at (analiz edilemez)
    df = df[df[FIELD_PERSONEL_ADI].notna()].reset_index(drop=True)

    # Ham tarih metnini sakla (hatalı tarih tespiti için)
    raw_date_col = df[FIELD_BITIS_TARIHI]
    parsed_dates = parse_date_series(raw_date_col)
    df[FIELD_BITIS_TARIHI] = parsed_dates

    # Hatalı tarih: orijinal hücre doluydu ama ayrıştırma başarısız oldu
    had_raw_value = raw_date_col.notna() & (raw_date_col.astype("string").str.strip() != "")
    df[COL_TARIH_HATALI] = had_raw_value & parsed_dates.isna()

    # Eksik belge: belge adı boş
    df[COL_BELGE_EKSIK] = df[FIELD_BELGE_ADI].isna()

    # Kalan gün + durum
    df[COL_KALAN_GUN] = calculate_remaining_days(df[FIELD_BITIS_TARIHI])
    df[COL_DURUM] = classify_status(df[COL_KALAN_GUN], thresholds)

    # Belge adı eksikse durum bilgisini de "Tarih Yok" gibi ele almak yerine
    # ayrı bir bayrakla zaten işaretledik; durum sütunu kalan güne göre kalır.

    employee_df = build_employee_summary(df)
    summary = build_summary(df, employee_df)

    return ProcessedData(detail_df=df, employee_df=employee_df, summary=summary)


def build_employee_summary(detail_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aynı personelin birden fazla satırını tek bir personel kartına
    (satırına) indirger. Her personel için belge sayıları ve en riskli
    durumu özetler.
    """
    if detail_df.empty:
        return pd.DataFrame(
            columns=[
                FIELD_PERSONEL_ADI, FIELD_UNVAN, "toplam_belge",
                "sure_gecmis", "kritik", "yaklasiyor", "gecerli",
                "tarih_yok", "en_riskli_durum", "min_kalan_gun",
            ]
        )

    grouped = detail_df.groupby([FIELD_PERSONEL_ADI, FIELD_UNVAN], dropna=False)

    agg = grouped.agg(
        toplam_belge=(FIELD_BELGE_ADI, "count"),
        min_kalan_gun=(COL_KALAN_GUN, "min"),
    ).reset_index()

    status_counts = (
        detail_df.groupby([FIELD_PERSONEL_ADI, FIELD_UNVAN, COL_DURUM], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    from models.document_status import (
        STATUS_CRITICAL,
        STATUS_EXPIRED,
        STATUS_UPCOMING,
        STATUS_VALID,
    )

    for status_col in (STATUS_EXPIRED, STATUS_CRITICAL, STATUS_UPCOMING, STATUS_VALID, STATUS_MISSING):
        if status_col not in status_counts.columns:
            status_counts[status_col] = 0

    merged = agg.merge(status_counts, on=[FIELD_PERSONEL_ADI, FIELD_UNVAN], how="left")

    merged = merged.rename(
        columns={
            STATUS_EXPIRED: "sure_gecmis",
            STATUS_CRITICAL: "kritik",
            STATUS_UPCOMING: "yaklasiyor",
            STATUS_VALID: "gecerli",
            STATUS_MISSING: "tarih_yok",
        }
    )

    def _risk_level(row) -> str:
        if row.get("sure_gecmis", 0) > 0:
            return STATUS_EXPIRED
        if row.get("kritik", 0) > 0:
            return STATUS_CRITICAL
        if row.get("yaklasiyor", 0) > 0:
            return STATUS_UPCOMING
        if row.get("gecerli", 0) > 0:
            return STATUS_VALID
        return STATUS_MISSING

    merged["en_riskli_durum"] = merged.apply(_risk_level, axis=1)
    return merged


def build_summary(detail_df: pd.DataFrame, employee_df: pd.DataFrame) -> ProcessingSummary:
    from models.document_status import STATUS_CRITICAL, STATUS_EXPIRED, STATUS_UPCOMING

    status_series = detail_df[COL_DURUM]
    return ProcessingSummary(
        total_employees=employee_df[FIELD_PERSONEL_ADI].nunique(),
        total_titles=employee_df[FIELD_UNVAN].nunique(),
        total_documents=int(detail_df[FIELD_BELGE_ADI].notna().sum()),
        expired_count=int((status_series == STATUS_EXPIRED).sum()),
        critical_count=int((status_series == STATUS_CRITICAL).sum()),
        upcoming_count=int((status_series == STATUS_UPCOMING).sum()),
        missing_document_count=int(detail_df[COL_BELGE_EKSIK].sum()),
        missing_date_count=int((status_series == STATUS_MISSING).sum() - int(detail_df[COL_TARIH_HATALI].sum())),
        invalid_date_count=int(detail_df[COL_TARIH_HATALI].sum()),
    )


def filter_detail_df(
    df: pd.DataFrame,
    unvan: list[str] | None = None,
    belge_turu: list[str] | None = None,
    personel: str | None = None,
    durum: list[str] | None = None,
    ay: list[int] | None = None,
    yil: list[int] | None = None,
) -> pd.DataFrame:
    """Sol panel filtrelerini DataFrame üzerine uygular."""
    out = df.copy()

    if unvan:
        out = out[out[FIELD_UNVAN].isin(unvan)]
    if belge_turu:
        out = out[out[FIELD_BELGE_ADI].isin(belge_turu)]
    if personel:
        out = out[out[FIELD_PERSONEL_ADI].str.contains(personel, case=False, na=False)]
    if durum:
        out = out[out[COL_DURUM].isin(durum)]
    if ay:
        out = out[out[FIELD_BITIS_TARIHI].dt.month.isin(ay)]
    if yil:
        out = out[out[FIELD_BITIS_TARIHI].dt.year.isin(yil)]

    return out
