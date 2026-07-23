"""
filters.py
----------
Sol panelde (sidebar) render edilen filtre kontrollerini oluşturur
ve seçilen filtre değerlerini döner.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from models.document_status import STATUS_ORDER
from services.data_processor import COL_DURUM
from utils.column_mapper import FIELD_BELGE_ADI, FIELD_BITIS_TARIHI, FIELD_PERSONEL_ADI, FIELD_UNVAN


@dataclass
class FilterState:
    unvan: list[str]
    belge_turu: list[str]
    personel: str
    durum: list[str]
    ay: list[int]
    yil: list[int]


AY_ISIMLERI = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}


def render_sidebar_filters(detail_df: pd.DataFrame) -> FilterState:
    st.sidebar.header("🔍 Filtreler")

    unvanlar = sorted(detail_df[FIELD_UNVAN].dropna().unique().tolist())
    selected_unvan = st.sidebar.multiselect("Ünvan", unvanlar, default=[])

    belge_turleri = sorted(detail_df[FIELD_BELGE_ADI].dropna().unique().tolist())
    selected_belge = st.sidebar.multiselect("Belge Türü", belge_turleri, default=[])

    selected_durum = st.sidebar.multiselect("Belge Durumu", STATUS_ORDER, default=[])

    valid_dates = detail_df[FIELD_BITIS_TARIHI].dropna()
    if not valid_dates.empty:
        years = sorted(valid_dates.dt.year.unique().tolist())
        selected_year = st.sidebar.multiselect("Yıl", years, default=[])
    else:
        selected_year = []

    months = list(range(1, 13))
    selected_month_labels = st.sidebar.multiselect(
        "Ay", [AY_ISIMLERI[m] for m in months], default=[]
    )
    selected_month = [m for m in months if AY_ISIMLERI[m] in selected_month_labels]

    st.sidebar.markdown("---")
    search_term = st.sidebar.text_input("👤 Personel Ara", placeholder="İsim yazın...")

    if st.sidebar.button("🔄 Filtreleri Temizle", use_container_width=True):
        st.rerun()

    return FilterState(
        unvan=selected_unvan,
        belge_turu=selected_belge,
        personel=search_term.strip() if search_term else "",
        durum=selected_durum,
        ay=selected_month,
        yil=selected_year,
    )
