"""
charts.py
---------
Dashboard için tüm Plotly görselleştirmeleri.
Kurumsal renk paleti kullanılır ve dark/light mod ile uyumludur.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from models.document_status import STATUS_COLORS, STATUS_ORDER
from services.data_processor import COL_DURUM, COL_KALAN_GUN
from utils.column_mapper import FIELD_BELGE_ADI, FIELD_BITIS_TARIHI, FIELD_PERSONEL_ADI, FIELD_UNVAN

CHART_TEMPLATE = "plotly_white"
CORPORATE_PALETTE = ["#1F3B57", "#2E6F95", "#4FA5C5", "#7FC8E0", "#B8E1EE", "#0B5563"]


def _empty_state(message: str = "Gösterilecek veri bulunamadı.") -> None:
    st.info(message)


def render_status_distribution(detail_df: pd.DataFrame) -> None:
    st.subheader("📊 Belge Durumu Dağılımı")
    if detail_df.empty:
        return _empty_state()

    counts = detail_df[COL_DURUM].value_counts().reindex(STATUS_ORDER, fill_value=0).reset_index()
    counts.columns = ["Durum", "Adet"]

    fig = px.pie(
        counts,
        names="Durum",
        values="Adet",
        color="Durum",
        color_discrete_map=STATUS_COLORS,
        hole=0.45,
        template=CHART_TEMPLATE,
    )
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


def render_expired_by_title(detail_df: pd.DataFrame) -> None:
    st.subheader("🚨 Ünvana Göre Süresi Geçmiş Belgeler")
    from models.document_status import STATUS_EXPIRED

    subset = detail_df[detail_df[COL_DURUM] == STATUS_EXPIRED]
    if subset.empty:
        return _empty_state("Süresi geçmiş belge bulunmuyor. 🎉")

    counts = subset.groupby(FIELD_UNVAN).size().sort_values(ascending=True).reset_index(name="Adet")

    fig = px.bar(
        counts,
        x="Adet",
        y=FIELD_UNVAN,
        orientation="h",
        template=CHART_TEMPLATE,
        color_discrete_sequence=[STATUS_COLORS[STATUS_EXPIRED]],
        text="Adet",
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), yaxis_title="", xaxis_title="Belge Sayısı")
    st.plotly_chart(fig, use_container_width=True)


def render_monthly_expiry(detail_df: pd.DataFrame) -> None:
    st.subheader("📅 Aylara Göre Bitecek Belgeler")
    subset = detail_df[detail_df[FIELD_BITIS_TARIHI].notna() & (detail_df[COL_KALAN_GUN] >= 0)]
    if subset.empty:
        return _empty_state()

    subset = subset.copy()
    subset["Ay-Yil"] = subset[FIELD_BITIS_TARIHI].dt.to_period("M").astype(str)
    counts = subset.groupby("Ay-Yil").size().reset_index(name="Adet").sort_values("Ay-Yil")

    fig = px.bar(
        counts,
        x="Ay-Yil",
        y="Adet",
        template=CHART_TEMPLATE,
        color_discrete_sequence=[CORPORATE_PALETTE[1]],
        text="Adet",
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), xaxis_title="Ay", yaxis_title="Belge Sayısı")
    st.plotly_chart(fig, use_container_width=True)


def render_document_type_distribution(detail_df: pd.DataFrame) -> None:
    st.subheader("📁 Belge Türlerine Göre Dağılım")
    subset = detail_df[detail_df[FIELD_BELGE_ADI].notna()]
    if subset.empty:
        return _empty_state()

    counts = subset[FIELD_BELGE_ADI].value_counts().head(15).reset_index()
    counts.columns = ["Belge Türü", "Adet"]

    fig = px.bar(
        counts,
        x="Adet",
        y="Belge Türü",
        orientation="h",
        template=CHART_TEMPLATE,
        color_discrete_sequence=[CORPORATE_PALETTE[2]],
        text="Adet",
    )
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        yaxis={"categoryorder": "total ascending"},
        yaxis_title="",
        xaxis_title="Belge Sayısı",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_riskiest_employees(employee_df: pd.DataFrame, top_n: int = 10) -> None:
    st.subheader("⚠️ En Riskli Personeller")
    if employee_df.empty:
        return _empty_state()

    subset = employee_df.copy()
    subset["risk_skoru"] = subset["sure_gecmis"] * 3 + subset["kritik"] * 2 + subset["yaklasiyor"]
    subset = subset.sort_values("risk_skoru", ascending=False).head(top_n)
    subset = subset[subset["risk_skoru"] > 0]

    if subset.empty:
        return _empty_state("Riskli personel bulunmuyor. 🎉")

    fig = px.bar(
        subset.sort_values("risk_skoru"),
        x="risk_skoru",
        y=FIELD_PERSONEL_ADI,
        orientation="h",
        template=CHART_TEMPLATE,
        color_discrete_sequence=[CORPORATE_PALETTE[0]],
        hover_data={FIELD_UNVAN: True, "sure_gecmis": True, "kritik": True, "yaklasiyor": True},
        text="risk_skoru",
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), yaxis_title="", xaxis_title="Risk Skoru")
    st.plotly_chart(fig, use_container_width=True)


def render_riskiest_titles(employee_df: pd.DataFrame, top_n: int = 10) -> None:
    st.subheader("🎯 En Riskli Ünvanlar")
    if employee_df.empty:
        return _empty_state()

    grouped = employee_df.groupby(FIELD_UNVAN).agg(
        sure_gecmis=("sure_gecmis", "sum"),
        kritik=("kritik", "sum"),
        yaklasiyor=("yaklasiyor", "sum"),
        personel_sayisi=(FIELD_PERSONEL_ADI, "nunique"),
    ).reset_index()

    grouped = grouped[(grouped["sure_gecmis"] + grouped["kritik"] + grouped["yaklasiyor"]) > 0]
    grouped = grouped.sort_values("sure_gecmis", ascending=False).head(top_n)

    if grouped.empty:
        return _empty_state("Riskli ünvan bulunmuyor. 🎉")

    fig = go.Figure()
    from models.document_status import STATUS_CRITICAL, STATUS_EXPIRED, STATUS_UPCOMING

    fig.add_bar(name="Süresi Geçmiş", x=grouped[FIELD_UNVAN], y=grouped["sure_gecmis"], marker_color=STATUS_COLORS[STATUS_EXPIRED])
    fig.add_bar(name="Kritik", x=grouped[FIELD_UNVAN], y=grouped["kritik"], marker_color=STATUS_COLORS[STATUS_CRITICAL])
    fig.add_bar(name="Yaklaşıyor", x=grouped[FIELD_UNVAN], y=grouped["yaklasiyor"], marker_color=STATUS_COLORS[STATUS_UPCOMING])
    fig.update_layout(barmode="stack", template=CHART_TEMPLATE, margin=dict(t=10, b=10, l=10, r=10), yaxis_title="Belge Sayısı")
    st.plotly_chart(fig, use_container_width=True)


def render_title_breakdown(employee_df: pd.DataFrame) -> None:
    st.subheader("🏷️ Ünvana Göre Personel ve Risk Dağılımı")
    if employee_df.empty:
        return _empty_state()

    grouped = employee_df.groupby(FIELD_UNVAN).agg(
        personel_sayisi=(FIELD_PERSONEL_ADI, "nunique"),
        sure_gecmis=("sure_gecmis", "sum"),
        kritik=("kritik", "sum"),
        yaklasiyor=("yaklasiyor", "sum"),
    ).reset_index().sort_values("personel_sayisi", ascending=False)

    grouped.columns = ["Ünvan", "Personel Sayısı", "Süresi Geçmiş Belge", "Kritik Belge", "Yaklaşan Belge"]
    st.dataframe(grouped, use_container_width=True, hide_index=True)
