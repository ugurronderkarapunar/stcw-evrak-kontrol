"""
column_mapper.py
-----------------
Yüklenen Excel/CSV dosyalarındaki kolon isimleri sabit olmayabilir.
Bu modül, benzer/eşanlamlı kolon adlarını otomatik olarak standart
alanlara (personel_adi, unvan, belge_adi, bitis_tarihi ...) eşler.

Yaklaşım:
1. Kolon adını normalize et (küçük harf, Türkçe karakter sadeleştirme,
   boşluk/alt çizgi temizliği).
2. Bilinen eşanlamlı sözlükle tam/parçalı eşleşme ara.
3. Eşleşme bulunamazsa None döner; kullanıcı arayüzden manuel seçer.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

# Standart alan adları
FIELD_PERSONEL_ADI = "personel_adi"
FIELD_UNVAN = "unvan"
FIELD_BELGE_ADI = "belge_adi"
FIELD_BITIS_TARIHI = "bitis_tarihi"
FIELD_BASLANGIC_TARIHI = "baslangic_tarihi"

REQUIRED_FIELDS = [FIELD_PERSONEL_ADI, FIELD_BELGE_ADI, FIELD_BITIS_TARIHI]

# Her standart alan için olası kolon isimleri (normalize edilmiş haliyle
# karşılaştırılacak). Sıra önemli değildir; en uzun/eşleşen skor kazanır.
SYNONYMS: dict[str, list[str]] = {
    FIELD_PERSONEL_ADI: [
        "personel adi", "personel", "ad soyad", "adi soyadi", "adsoyad",
        "employee", "employee name", "crew", "crew name", "isim", "personel ismi",
        "calisan", "calisan adi", "full name", "name", "seafarer", "seafarer name",
    ],
    FIELD_UNVAN: [
        "unvan", "gorev", "rank", "position", "title", "pozisyon",
        "job title", "rutbe", "meslek",
    ],
    FIELD_BELGE_ADI: [
        "belge adi", "certificate", "document", "belge", "sertifika",
        "certificate name", "document name", "belge turu", "document type",
        "evrak", "evrak adi",
    ],
    FIELD_BITIS_TARIHI: [
        "bitis tarihi", "expiration", "expiry", "son gecerlilik",
        "valid until", "expiry date", "expiration date", "gecerlilik tarihi",
        "son kullanma tarihi", "end date", "sona erme tarihi",
    ],
    FIELD_BASLANGIC_TARIHI: [
        "belge tarihi", "baslangic tarihi", "issue date", "duzenlenme tarihi",
        "verilis tarihi", "start date",
    ],
}


def _normalize(text: str) -> str:
    """Türkçe karakterleri sadeleştirir, küçük harfe çevirir, boşlukları sadeleştirir."""
    if text is None:
        return ""
    text = str(text).strip().lower()
    tr_map = str.maketrans("çğıöşü", "cgiosu")
    text = text.translate(tr_map)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class ColumnMapping:
    mapping: dict[str, str | None] = field(default_factory=dict)  # standart_alan -> orijinal_kolon
    unmatched_columns: list[str] = field(default_factory=list)

    def missing_required(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if not self.mapping.get(f)]

    def is_valid(self) -> bool:
        return len(self.missing_required()) == 0


def auto_map_columns(columns: list[str]) -> ColumnMapping:
    """Verilen kolon listesini standart alanlara otomatik eşler."""
    normalized_cols = {col: _normalize(col) for col in columns}
    result = ColumnMapping()
    used_columns: set[str] = set()

    for field_name, synonyms in SYNONYMS.items():
        best_col = None
        best_score = 0
        norm_synonyms = [_normalize(s) for s in synonyms]

        for orig_col, norm_col in normalized_cols.items():
            if orig_col in used_columns:
                continue
            score = 0
            if norm_col in norm_synonyms:
                score = 100
            else:
                for syn in norm_synonyms:
                    if syn in norm_col or norm_col in syn:
                        score = max(score, len(syn))
            if score > best_score:
                best_score = score
                best_col = orig_col

        if best_col:
            result.mapping[field_name] = best_col
            used_columns.add(best_col)
        else:
            result.mapping[field_name] = None

    result.unmatched_columns = [c for c in columns if c not in used_columns]
    return result


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    """Eşlemeye göre DataFrame'i standart kolon adlarıyla yeniden oluşturur."""
    out = pd.DataFrame()
    for standard_field, orig_col in mapping.items():
        if orig_col and orig_col in df.columns:
            out[standard_field] = df[orig_col]
        else:
            out[standard_field] = pd.NA
    return out
