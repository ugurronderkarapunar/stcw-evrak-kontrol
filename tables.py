"""
tables.py
---------
Dashboard'daki detay tablolarını (süresi geçmiş, 30/90 gün, eksik,
hatalı tarih) render eden bileşenler.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from models.document_status import STATUS_CRITICAL, STATUS_EXPIRED, STATUS_UPCOMING
from services.data_processor import COL_BELGE_EKSIK, COL_DURUM, COL_KALAN_GUN, COL_TARIH_HATALI
from services.report_generator import to_csv_bytes, to_excel_bytes, to_pdf_bytes
from utils.column_mapper import FIELD_BELGE_ADI, FIELD_BITIS_TARIHI, FIELD_PERSONEL_ADI, FIELD_UNVAN


def _download_row(df: pd.DataFrame, base_name: str, pdf_title: str, key_prefix: str) -> None:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "⬇️ Excel indir",
            data=to_excel_bytes({base_name[:31]: df}),
            file_name=f"{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_xlsx",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "⬇️ CSV indir",
            data=to_csv_bytes(df),
            file_name=f"{base_name}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            use_container_width=True,
        )
    with col3:
        st.download_button(
            "⬇️ PDF indir",
            data=to_pdf_bytes(pdf_title, df),
            file_name=f"{base_name}.pdf",
            mime="application/pdf",
            key=f"{key_prefix}_pdf",
            use_container_width=True,
        )


def render_expired_table(detail_df: pd.DataFrame) -> None:
    st.markdown("#### 🔴 Süresi Geçmiş Personeller")
    subset = detail_df[detail_df[COL_DURUM] == STATUS_EXPIRED].copy()
    if subset.empty:
        st.success("Süresi geçmiş belge bulunmuyor.")
        return

    subset["Kaç Gün Geçmiş"] = subset[COL_KALAN_GUN].abs().astype(int)
    display_df = subset[[FIELD_PERSONEL_ADI, FIELD_UNVAN, FIELD_BELGE_ADI, FIELD_BITIS_TARIHI, "Kaç Gün Geçmiş"]]
    display_df.columns = ["Ad Soyad", "Ünvan", "Belge", "Bitiş Tarihi", "Kaç Gün Geçmiş"]
    display_df = display_df.sort_values("Kaç Gün Geçmiş", ascending=False)

    st.dataframe(_format_dates(display_df), use_container_width=True, hide_index=True)
    _download_row(display_df, "sure_gecmis_belgeler", "Süresi Geçmiş Belgeler Raporu", "expired")


def render_upcoming_table(detail_df: pd.DataFrame, status: str, title: str, icon: str) -> None:
    st.markdown(f"#### {icon} {title}")
    subset = detail_df[detail_df[COL_DURUM] == status].copy()
    if subset.empty:
        st.info("Bu kategoride belge bulunmuyor.")
        return

    subset["Kalan Gün"] = subset[COL_KALAN_GUN].astype(int)
    display_df = subset[[FIELD_PERSONEL_ADI, FIELD_UNVAN, FIELD_BELGE_ADI, FIELD_BITIS_TARIHI, "Kalan Gün"]]
    display_df.columns = ["Ad Soyad", "Ünvan", "Belge", "Bitiş Tarihi", "Kalan Gün"]
    display_df = display_df.sort_values("Kalan Gün")

    st.dataframe(_format_dates(display_df), use_container_width=True, hide_index=True)
    key = "critical" if status == STATUS_CRITICAL else "upcoming"
    _download_row(display_df, f"{key}_belgeler", title, key)


def render_missing_documents_table(detail_df: pd.DataFrame) -> None:
    st.markdown("#### 📭 Eksik Belgeler")
    subset = detail_df[detail_df[COL_BELGE_EKSIK]].copy()
    if subset.empty:
        st.success("Eksik belge kaydı bulunmuyor.")
        return

    display_df = subset[[FIELD_PERSONEL_ADI, FIELD_UNVAN]].drop_duplicates()
    display_df.columns = ["Ad Soyad", "Ünvan"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    _download_row(display_df, "eksik_belgeler", "Eksik Belgeler Raporu", "missing_doc")


def render_invalid_dates_table(detail_df: pd.DataFrame) -> None:
    st.markdown("#### ⚠️ Hatalı Tarihler")
    subset = detail_df[detail_df[COL_TARIH_HATALI]].copy()
    if subset.empty:
        st.success("Hatalı tarih kaydı bulunmuyor.")
        return

    display_df = subset[[FIELD_PERSONEL_ADI, FIELD_UNVAN, FIELD_BELGE_ADI]]
    display_df.columns = ["Ad Soyad", "Ünvan", "Belge"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    _download_row(display_df, "hatali_tarihler", "Hatalı Tarih Raporu", "invalid_date")


def render_employee_card_table(employee_df: pd.DataFrame, detail_df: pd.DataFrame) -> None:
    """Her personeli tek kart/satırda, tüm belgelerini özetleyerek gösterir."""
    st.markdown("#### 👤 Personel Bazlı Özet")
    if employee_df.empty:
        st.info("Gösterilecek personel bulunmuyor.")
        return

    for _, row in employee_df.sort_values("sure_gecmis", ascending=False).iterrows():
        icon = "🔴" if row["sure_gecmis"] > 0 else "🟠" if row["kritik"] > 0 else "🟡" if row["yaklasiyor"] > 0 else "🟢"
        with st.expander(f"{icon} {row[FIELD_PERSONEL_ADI]} — {row[FIELD_UNVAN]}  ({int(row['toplam_belge'])} belge)"):
            docs = detail_df[
                (detail_df[FIELD_PERSONEL_ADI] == row[FIELD_PERSONEL_ADI])
                & (detail_df[FIELD_UNVAN] == row[FIELD_UNVAN])
            ][[FIELD_BELGE_ADI, FIELD_BITIS_TARIHI, COL_DURUM, COL_KALAN_GUN]].copy()
            docs.columns = ["Belge", "Bitiş Tarihi", "Durum", "Kalan Gün"]
            st.dataframe(_format_dates(docs), use_container_width=True, hide_index=True)


def _format_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%d.%m.%Y")
    return out
