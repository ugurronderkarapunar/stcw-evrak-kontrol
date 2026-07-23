"""
kpi_cards.py
------------
Üst KPI kartlarını render eden bileşen.
"""

from __future__ import annotations

import streamlit as st

from services.data_processor import ProcessingSummary


def render_kpi_cards(summary: ProcessingSummary) -> None:
    cards = [
        ("👥", "Toplam Personel", summary.total_employees, None),
        ("🏷️", "Toplam Ünvan", summary.total_titles, None),
        ("📄", "Toplam Belge", summary.total_documents, None),
        ("🔴", "Süresi Geçmiş", summary.expired_count, "expired"),
        ("🟠", "30 Gün İçinde", summary.critical_count, "critical"),
        ("🟡", "90 Gün İçinde", summary.upcoming_count, "upcoming"),
        ("📭", "Eksik Belge", summary.missing_document_count, None),
        ("❓", "Hatalı/Eksik Tarih", summary.missing_date_count + summary.invalid_date_count, None),
    ]

    cols = st.columns(len(cards))
    for col, (icon, label, value, tone) in zip(cols, cards):
        tone_class = f" kpi-{tone}" if tone else ""
        formatted_value = f"{value:,}".replace(",", ".")
        with col:
            st.markdown(
                f"""
                <div class="kpi-card{tone_class}">
                    <div class="kpi-icon">{icon}</div>
                    <div class="kpi-value">{formatted_value}</div>
                    <div class="kpi-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
