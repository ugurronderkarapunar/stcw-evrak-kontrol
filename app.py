"""
app.py
------
Personel Belge Takip Sistemi — ana giriş noktası.

Bu dosya sade bir orkestrasyon katmanı olarak tasarlanmıştır:
tüm iş mantığı services/ ve utils/ içinde, tüm görsel bileşenler
components/ içinde yer alır. app.py yalnızca bunları birleştirir.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.filters import render_sidebar_filters
from components.kpi_cards import render_kpi_cards
from components.tables import (
    render_employee_card_table,
    render_expired_table,
    render_invalid_dates_table,
    render_missing_documents_table,
    render_upcoming_table,
)
from components import charts
from models.document_status import STATUS_CRITICAL, STATUS_UPCOMING, StatusThresholds
from services.data_processor import build_employee_summary, build_summary, filter_detail_df, process_dataframe
from services.file_loader import FileLoadError, get_sheet_names, load_file
from services.report_generator import to_csv_bytes, to_excel_bytes, to_pdf_bytes
from utils.column_mapper import (
    REQUIRED_FIELDS,
    ColumnMapping,
    auto_map_columns,
)

APP_TITLE = "Personel Belge Takip Sistemi"
FIELD_LABELS = {
    "personel_adi": "Personel Adı",
    "unvan": "Ünvan",
    "belge_adi": "Belge Adı",
    "bitis_tarihi": "Bitiş Tarihi",
    "baslangic_tarihi": "Belge (Başlangıç) Tarihi",
}


def _inject_css() -> None:
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _render_header() -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div>
                <h1>📋 {APP_TITLE}</h1>
                <p>Kurumsal belge geçerlilik takibi ve risk analizi</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_column_mapping_ui(columns: list[str], mapping: ColumnMapping) -> dict[str, str | None]:
    """Otomatik eşleşmeyen veya kullanıcının düzeltmek isteyebileceği kolonlar için manuel seçim sunar."""
    st.warning(
        "Bazı zorunlu kolonlar otomatik olarak tespit edilemedi. "
        "Lütfen aşağıdan doğru kolonları eşleştirin."
    )
    resolved: dict[str, str | None] = dict(mapping.mapping)
    options = ["— Seçilmedi —"] + columns

    cols = st.columns(len(REQUIRED_FIELDS) + 1)
    all_fields = list(FIELD_LABELS.keys())
    for i, field_name in enumerate(all_fields):
        current = mapping.mapping.get(field_name)
        default_index = options.index(current) if current in options else 0
        with cols[i % len(cols)]:
            selected = st.selectbox(
                FIELD_LABELS[field_name],
                options,
                index=default_index,
                key=f"map_{field_name}",
            )
        resolved[field_name] = None if selected == "— Seçilmedi —" else selected
    return resolved


def _handle_upload() -> None:
    uploaded_file = st.file_uploader(
        "Excel (.xlsx) veya CSV dosyanızı yükleyin",
        type=["xlsx", "xls", "csv", "xlsm"],
        help="Personel adı, ünvan, belge adı ve bitiş tarihi kolonlarını içeren bir dosya yükleyin.",
    )

    if uploaded_file is None:
        st.info("Analiz başlatmak için bir dosya yükleyin.")
        st.markdown(
            """
            **Beklenen kolonlar (isimler esnektir, otomatik tespit edilir):**
            - Personel Adı / Ad Soyad / Employee / Crew
            - Ünvan / Görev / Rank / Position
            - Belge Adı / Certificate / Document
            - Bitiş Tarihi / Expiry / Valid Until
            """
        )
        return

    sheet_names = get_sheet_names(uploaded_file)
    selected_sheet = 0
    if sheet_names and len(sheet_names) > 1:
        selected_sheet = st.selectbox("Sayfa (Sheet) Seçin", sheet_names, index=0)

    try:
        load_result = load_file(uploaded_file, sheet_name=selected_sheet)
    except FileLoadError as e:
        st.error(f"❌ {e}")
        return

    mapping = auto_map_columns(list(load_result.dataframe.columns))

    if not mapping.is_valid():
        resolved = _render_column_mapping_ui(list(load_result.dataframe.columns), mapping)
        mapping.mapping = resolved
        if not mapping.is_valid():
            missing_labels = ", ".join(FIELD_LABELS[f] for f in mapping.missing_required())
            st.error(f"❌ Zorunlu kolonlar eksik: {missing_labels}. Lütfen eşleştirmeyi tamamlayın.")
            return

    with st.expander("⚙️ Kolon Eşleştirmesini Görüntüle / Düzenle"):
        resolved = _render_column_mapping_ui(list(load_result.dataframe.columns), mapping)
        mapping.mapping = resolved

    with st.sidebar.expander("⚙️ Durum Eşikleri", expanded=False):
        critical_days = st.slider("Kritik eşik (gün)", 7, 60, 30)
        upcoming_days = st.slider("Yaklaşıyor eşik (gün)", 61, 180, 90)

    thresholds = StatusThresholds(critical_days=critical_days, upcoming_days=upcoming_days)

    try:
        processed = process_dataframe(load_result.dataframe, mapping, thresholds)
    except Exception as e:  # noqa: BLE001
        st.error(
            "❌ Veri işlenirken beklenmeyen bir hata oluştu. "
            "Lütfen kolon eşleştirmesini kontrol edin."
        )
        with st.expander("Teknik detay"):
            st.exception(e)
        return

    st.session_state["processed"] = processed
    st.success(
        f"✅ {load_result.row_count} satır başarıyla işlendi "
        f"({processed.summary.total_employees} personel, {processed.summary.total_documents} belge)."
    )


def _render_dashboard() -> None:
    processed = st.session_state.get("processed")
    if processed is None:
        return

    detail_df = processed.detail_df
    employee_df = processed.employee_df

    filters = render_sidebar_filters(detail_df)
    filtered_df = filter_detail_df(
        detail_df,
        unvan=filters.unvan or None,
        belge_turu=filters.belge_turu or None,
        personel=filters.personel or None,
        durum=filters.durum or None,
        ay=filters.ay or None,
        yil=filters.yil or None,
    )

    filtered_employee_df = build_employee_summary(filtered_df)

    st.markdown("### 📈 Genel Özet")
    filtered_summary = build_summary(filtered_df, filtered_employee_df)
    render_kpi_cards(filtered_summary)

    tabs = st.tabs(
        ["📊 Grafikler", "📋 Tablolar", "👤 Personel Kartları", "⬇️ Raporlar"]
    )

    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            charts.render_status_distribution(filtered_df)
        with col2:
            charts.render_document_type_distribution(filtered_df)

        col3, col4 = st.columns(2)
        with col3:
            charts.render_expired_by_title(filtered_df)
        with col4:
            charts.render_monthly_expiry(filtered_df)

        col5, col6 = st.columns(2)
        with col5:
            charts.render_riskiest_employees(filtered_employee_df)
        with col6:
            charts.render_riskiest_titles(filtered_employee_df)

        charts.render_title_breakdown(filtered_employee_df)

    with tabs[1]:
        render_expired_table(filtered_df)
        st.markdown("---")
        render_upcoming_table(filtered_df, STATUS_CRITICAL, "30 Gün İçinde Bitecekler", "🟠")
        st.markdown("---")
        render_upcoming_table(filtered_df, STATUS_UPCOMING, "90 Gün İçinde Bitecekler", "🟡")
        st.markdown("---")
        render_missing_documents_table(filtered_df)
        st.markdown("---")
        render_invalid_dates_table(filtered_df)

    with tabs[2]:
        render_employee_card_table(filtered_employee_df, filtered_df)

    with tabs[3]:
        st.markdown("#### Tüm Filtrelenmiş Veriyi Dışa Aktar")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "⬇️ Excel (tüm sayfalar)",
                data=to_excel_bytes(
                    {
                        "Tum_Belgeler": filtered_df,
                        "Personel_Ozet": filtered_employee_df,
                    }
                ),
                file_name="personel_belge_raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                "⬇️ CSV",
                data=to_csv_bytes(filtered_df),
                file_name="personel_belge_raporu.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col3:
            summary_lines = [
                f"Toplam Personel: {filtered_summary.total_employees}",
                f"Süresi Geçmiş Belge: {filtered_summary.expired_count}",
                f"Kritik (30 gün): {filtered_summary.critical_count}",
            ]
            st.download_button(
                "⬇️ PDF (özet)",
                data=to_pdf_bytes("Personel Belge Takip Raporu", filtered_df, summary_lines),
                file_name="personel_belge_raporu.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()
    _render_header()
    _handle_upload()
    st.markdown("---")
    _render_dashboard()


if __name__ == "__main__":
    main()
