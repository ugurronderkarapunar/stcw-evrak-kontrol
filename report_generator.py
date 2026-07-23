"""
report_generator.py
--------------------
Dashboard verilerini Excel, CSV ve PDF formatlarında dışa aktarır.
"""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd


def to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Birden fazla DataFrame'i çok sayfalı bir Excel dosyasına yazar."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31]  # Excel sayfa adı sınırı
            export_df = _prepare_for_export(df)
            export_df.to_excel(writer, sheet_name=safe_name, index=False)
            _autosize_columns(writer, safe_name, export_df)
    return buffer.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    export_df = _prepare_for_export(df)
    return export_df.to_csv(index=False).encode("utf-8-sig")


def to_pdf_bytes(title: str, df: pd.DataFrame, summary_lines: list[str] | None = None) -> bytes:
    """
    Basit, kurumsal görünümlü tablo raporu üretir (reportlab).
    Çok büyük tabloları (>500 satır) sınırlandırır; PDF yalnızca
    özet/öncelikli raporlar için uygundur.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"])]
    elements.append(Paragraph(f"Oluşturulma Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.4 * cm))

    if summary_lines:
        for line in summary_lines:
            elements.append(Paragraph(line, styles["Normal"]))
        elements.append(Spacer(1, 0.5 * cm))

    export_df = _prepare_for_export(df).head(500)
    data = [list(export_df.columns)] + export_df.astype(str).values.tolist()

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3B57")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)

    if len(export_df) < len(df):
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(
            Paragraph(
                f"Not: Tabloda toplam {len(df)} satırdan ilk {len(export_df)} tanesi gösterilmektedir. "
                f"Tam veri için Excel/CSV indirmesini kullanın.",
                styles["Italic"],
            )
        )

    doc.build(elements)
    return buffer.getvalue()


def _prepare_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Tarih kolonlarını okunabilir metne çevirir, teknik yardımcı kolonları gizler."""
    out = df.copy()
    hidden_cols = [c for c in out.columns if c.startswith("_")]
    out = out.drop(columns=hidden_cols, errors="ignore")

    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%d.%m.%Y").fillna("")
    return out


def _autosize_columns(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    from openpyxl.utils import get_column_letter

    worksheet = writer.sheets[sheet_name]
    for i, col in enumerate(df.columns, start=1):
        lengths = df[col].astype(str).str.len()
        raw_max = lengths.max() if len(df) else 0
        col_max = int(raw_max) if pd.notna(raw_max) else 0
        max_len = max(col_max, len(str(col))) + 2
        worksheet.column_dimensions[get_column_letter(i)].width = min(max_len, 40)
