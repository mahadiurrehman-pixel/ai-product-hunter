"""
REHU Sidebar — Grouped navigation, workspace, environment.

Uses st.button + st.switch_page for robust cross-version navigation.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from ui.helpers import MARKETPLACE_LABELS, safe_rerun

_LOGO_PATH = Path("ui/assets/rehu_logo.png")


def _nav(label: str, target: str, current: str, key: str):
    """Render a navigation button. Highlights if active."""
    active = (label == current)
    if st.button(
        label, key=key, use_container_width=True,
        type="primary" if active else "secondary",
    ):
        if not active:
            try:
                st.switch_page(target)
            except Exception:
                pass


def render_sidebar(current_page: str = "Search") -> str:
    """
    Render sidebar and return active marketplace code.

    Args:
        current_page: Label of the currently active page for highlighting.
    """
    marketplaces = ["US", "UK", "DE", "AU", "CA"]

    with st.sidebar:
        # --- Brand ---
        if _LOGO_PATH.exists():
            st.image(str(_LOGO_PATH), width=120)
        else:
            st.markdown(
                '<div style="font-size:24px;font-weight:700;color:#F1F5F9;'
                'padding:8px 0 2px 0;">REHU</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div style="color:#94A3B8;font-size:11px;margin:0 0 12px 0;">'
            "Product Research Intelligence</div>",
            unsafe_allow_html=True,
        )

        # --- RESEARCH ---
        st.markdown(
            '<div style="color:#64748B;font-size:10px;font-weight:700;'
            'letter-spacing:0.8px;margin:12px 0 6px 0;">RESEARCH</div>',
            unsafe_allow_html=True,
        )
        _nav("Search", "app.py", current_page, "nav_search")

        # --- TOOLS ---
        st.markdown(
            '<div style="color:#64748B;font-size:10px;font-weight:700;'
            'letter-spacing:0.8px;margin:16px 0 6px 0;">TOOLS</div>',
            unsafe_allow_html=True,
        )
        _nav("Profit Calculator", "pages/2_Profit_Calculator.py", current_page, "nav_calc")
        _nav("Opportunity Detail", "pages/1_Opportunity_Detail.py", current_page, "nav_detail")

        # --- MANAGE ---
        st.markdown(
            '<div style="color:#64748B;font-size:10px;font-weight:700;'
            'letter-spacing:0.8px;margin:16px 0 6px 0;">MANAGE</div>',
            unsafe_allow_html=True,
        )
        _nav("Watchlist", "pages/3_Watchlist.py", current_page, "nav_watch")

        st.divider()

        # --- WORKSPACE ---
        st.markdown(
            '<div style="color:#64748B;font-size:10px;font-weight:700;'
            'letter-spacing:0.8px;margin:0 0 6px 0;">MARKETPLACE</div>',
            unsafe_allow_html=True,
        )

        current_mp = st.session_state.get("marketplace", "US")
        labels = [MARKETPLACE_LABELS[m] for m in marketplaces]
        idx = marketplaces.index(current_mp) if current_mp in marketplaces else 0

        selected = st.selectbox(
            "Marketplace", labels, index=idx,
            key="sidebar_mp", label_visibility="collapsed",
        )
        selected_code = next(
            (k for k, v in MARKETPLACE_LABELS.items() if v == selected), "US"
        )

        if selected_code != st.session_state.get("marketplace"):
            st.session_state["marketplace"] = selected_code
            st.session_state["search_results"] = None
            st.session_state["supplier_map"] = {}
            st.session_state["selected_opportunity"] = None
            st.session_state["selected_category"] = None
            safe_rerun()

        st.divider()

        # --- ENVIRONMENT ---
        try:
            from config import settings
            env = getattr(settings, "ebay_environment", "sandbox").capitalize()
        except Exception:
            env = "Sandbox"

        st.markdown(
            f'<div style="color:#64748B;font-size:10px;font-weight:700;'
            f'letter-spacing:0.8px;margin:0 0 6px 0;">ENVIRONMENT</div>'
            f'<div style="color:#F1F5F9;font-size:13px;">{env}</div>'
            f'<div style="color:#94A3B8;font-size:11px;margin-top:4px;">'
            f"Supplier data: Simulated</div>",
            unsafe_allow_html=True,
        )

    return st.session_state.get("marketplace", "US")