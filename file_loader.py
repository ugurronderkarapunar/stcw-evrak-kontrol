"""
file_loader.py
---------------
Yüklenen Excel (.xlsx, .xls) veya CSV dosyalarını güvenli biçimde okur.
Kullanıcı dostu hata mesajları üretir; bozuk/desteklenmeyen dosyaları
uygulamayı çökertmeden yakalar.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd


class FileLoadError(Exception):
    """Kullanıcıya gösterilecek, anlaşılır dosya yükleme hatası."""


@dataclass
class LoadResult:
    dataframe: pd.DataFrame
    sheet_name: str | None
    row_count: int
    column_count: int


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".xlsm"}


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    """CSV'yi farklı ayraç/kodlama denemeleriyle okur."""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        for sep in (None, ";", ",", "\t"):
            try:
                buf = io.BytesIO(file_bytes)
                df = pd.read_csv(buf, encoding=encoding, sep=sep, engine="python")
                if df.shape[1] > 1 or sep is not None:
                    return df
            except Exception as e:  # noqa: BLE001
                last_error = e
                continue
    raise FileLoadError(
        "CSV dosyası okunamadı. Dosyanın bozuk olmadığından ve "
        "standart bir kodlama (UTF-8) kullandığından emin olun."
    ) from last_error


def load_file(uploaded_file, sheet_name: str | int | None = 0) -> LoadResult:
    """
    Streamlit'ten gelen UploadedFile nesnesini okur.

    Hatalar FileLoadError olarak fırlatılır; çağıran taraf (app.py)
    bunu kullanıcıya st.error ile gösterir.
    """
    if uploaded_file is None:
        raise FileLoadError("Herhangi bir dosya seçilmedi.")

    filename = getattr(uploaded_file, "name", "dosya")
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        raise FileLoadError(
            f"Desteklenmeyen dosya formatı: '{ext}'. "
            f"Lütfen .xlsx, .xls veya .csv formatında bir dosya yükleyin."
        )

    try:
        file_bytes = uploaded_file.getvalue()
    except AttributeError:
        file_bytes = uploaded_file.read()

    if not file_bytes:
        raise FileLoadError("Yüklenen dosya boş görünüyor. Lütfen içerik doğrulaması yapıp tekrar deneyin.")

    try:
        if ext == ".csv":
            df = _read_csv(file_bytes)
            resolved_sheet = None
        else:
            buf = io.BytesIO(file_bytes)
            try:
                excel_file = pd.ExcelFile(buf, engine="openpyxl" if ext != ".xls" else None)
            except Exception as e:  # noqa: BLE001
                raise FileLoadError(
                    "Excel dosyası açılamadı. Dosyanın bozuk olmadığından "
                    "ve şifreli olmadığından emin olun."
                ) from e

            sheets = excel_file.sheet_names
            if not sheets:
                raise FileLoadError("Excel dosyasında hiç sayfa (sheet) bulunamadı.")

            target_sheet = sheet_name if sheet_name in sheets else sheets[0] if isinstance(sheet_name, int) else sheet_name
            if isinstance(sheet_name, int):
                target_sheet = sheets[min(sheet_name, len(sheets) - 1)]
            elif sheet_name not in sheets:
                target_sheet = sheets[0]

            df = excel_file.parse(target_sheet)
            resolved_sheet = target_sheet
    except FileLoadError:
        raise
    except Exception as e:  # noqa: BLE001
        raise FileLoadError(
            "Dosya okunurken beklenmeyen bir hata oluştu. "
            "Dosyanın standart bir Excel/CSV formatında olduğundan emin olun."
        ) from e

    if df.empty:
        raise FileLoadError("Dosyada işlenecek veri satırı bulunamadı.")

    # Tamamen boş kolon/satırları temizle (bozuk şablonlarda sık görülür).
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    if df.shape[1] < 2:
        raise FileLoadError(
            "Dosyada yeterli sayıda kolon bulunamadı. "
            "En az Personel Adı, Belge Adı ve Bitiş Tarihi kolonları gereklidir."
        )

    return LoadResult(dataframe=df, sheet_name=resolved_sheet, row_count=len(df), column_count=df.shape[1])


def get_sheet_names(uploaded_file) -> list[str]:
    """Bir Excel dosyasındaki tüm sayfa isimlerini döner (CSV için boş liste)."""
    filename = getattr(uploaded_file, "name", "")
    if filename.lower().endswith(".csv"):
        return []
    try:
        file_bytes = uploaded_file.getvalue()
        buf = io.BytesIO(file_bytes)
        excel_file = pd.ExcelFile(buf, engine="openpyxl")
        return excel_file.sheet_names
    except Exception:  # noqa: BLE001
        return []
