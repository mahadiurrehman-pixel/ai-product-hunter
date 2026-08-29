"""
REHU — Watchlist (Session-State MVP)

Saved opportunities with notes, source links, export, and cross-navigation.
"""
from __future__ import annotations

import json
from datetime import datetime
import streamlit as st

from ui.helpers import (
    GLOBAL_CSS, init_session_state, safe_rerun,
    format_currency, format_percent, format_score, truncate,
    recommendation_html, policy_html, is_valid_url,
)
from ui.components.sidebar import render_sidebar


st.set_page_config(
    page_title="REHU — Watchlist",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
init_session_state()

render_sidebar(current_page="Watchlist")

st.markdown('<div class="rehu-title">Watchlist</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="rehu-subtitle">Opportunities saved for further review.</div>',
    unsafe_allow_html=True,
)

wl = st.session_state.get("watchlist", [])

if not wl:
    st.markdown(
        '<div class="rehu-empty">'
        "<h3>Your watchlist is empty</h3>"
        "<p>Save opportunities from Search to review them here.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# --- Actions Bar ---
a1, a2, a3, a4 = st.columns([2, 1, 1, 1])
with a1:
    st.markdown(
        f'<div style="font-size:13px;color:#64748B;padding-top:8px;">'
        f"{len(wl)} saved</div>", unsafe_allow_html=True,
    )
with a2:
    csv_header = "title,marketplace,currency,net_profit,margin,roi,score,recommendation,ebay_url,supplier_url,notes"
    csv_rows = [csv_header]
    for w in wl:
        csv_rows.append(",".join([
            (w.get("product_title") or "").replace(",", " "),
            w.get("marketplace", ""), w.get("currency", "USD"),
            str(w.get("net_profit", "")), str(w.get("margin", "")),
            str(w.get("roi", "")), str(w.get("final_score", "")),
            w.get("recommendation", ""),
            w.get("ebay_url") or "", w.get("supplier_url") or "",
            (w.get("notes") or "").replace(",", " ").replace("\n", " "),
        ]))
    st.download_button(
        "Export CSV", data="\n".join(csv_rows),
        file_name=f"rehu_watchlist_{datetime.utcnow().strftime('%Y%m%d')}.csv",
        mime="text/csv", use_container_width=True,
    )
with a3:
    st.download_button(
        "Export JSON", data=json.dumps(wl, indent=2, default=str),
        file_name=f"rehu_watchlist_{datetime.utcnow().strftime('%Y%m%d')}.json",
        mime="application/json", use_container_width=True,
    )
with a4:
    if st.button("Clear All", use_container_width=True, key="wl_clear"):
        st.session_state["watchlist"] = []
        safe_rerun()

st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

# --- Items ---
for idx, w in enumerate(list(wl)):
    cur = w.get("currency", "USD")
    with st.container():
        st.markdown('<div class="rehu-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([3, 2, 2])

        with c1:
            st.markdown(
                f'<div style="font-size:14px;font-weight:600;color:#0F172A;">'
                f"{truncate(w.get('product_title') or 'Untitled', 70)}</div>"
                f'<div style="font-size:12px;color:#64748B;margin-top:4px;">'
                f"{w.get('marketplace','--')} &middot; "
                f"Saved {w.get('saved_at','')[:10]}</div>",
                unsafe_allow_html=True,
            )
            notes = st.text_area(
                "Notes", value=w.get("notes", ""),
                key=f"wl_notes_{idx}", height=68,
                label_visibility="collapsed", placeholder="Add notes...",
            )
            if notes != w.get("notes", ""):
                st.session_state["watchlist"][idx]["notes"] = notes

        with c2:
            st.markdown(
                f'<div class="rehu-kv"><span class="rehu-kv-k">Score</span>'
                f'<span class="rehu-kv-v">{format_score(w.get("final_score", 0))}</span></div>'
                f'<div class="rehu-kv"><span class="rehu-kv-k">Profit</span>'
                f'<span class="rehu-kv-v" style="color:#047857;">'
                f'{format_currency(w.get("net_profit", 0), cur)}</span></div>'
                f'<div class="rehu-kv"><span class="rehu-kv-k">Margin</span>'
                f'<span class="rehu-kv-v">{format_percent(w.get("margin", 0))}</span></div>'
                f'<div style="margin-top:6px;">'
                f"{recommendation_html(w.get('recommendation','hold'))} "
                f"{policy_html(w.get('policy_risk','not_checked'))}</div>",
                unsafe_allow_html=True,
            )

        with c3:
            if is_valid_url(w.get("ebay_url")):
                st.markdown(
                    f'<a class="rehu-btn" href="{w["ebay_url"]}" target="_blank">View on eBay</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="rehu-btn-disabled">eBay unavailable</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)
            if is_valid_url(w.get("supplier_url")):
                st.markdown(
                    f'<a class="rehu-btn rehu-btn-secondary" href="{w["supplier_url"]}" '
                    f'target="_blank">View Supplier</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="rehu-btn-disabled">Supplier unavailable</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

            b1, b2 = st.columns(2)
            with b1:
                if st.button("Inspect", key=f"wl_insp_{idx}", use_container_width=True):
                    st.session_state["selected_opportunity"] = w
                    try:
                        st.switch_page("pages/1_Opportunity_Detail.py")
                    except Exception:
                        pass
            with b2:
                if st.button("Remove", key=f"wl_rm_{idx}", use_container_width=True):
                    st.session_state["watchlist"].pop(idx)
                    safe_rerun()

        st.markdown("</div>", unsafe_allow_html=True)