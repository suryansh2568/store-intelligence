"""
Streamlit web dashboard for Store Intelligence System.
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import time

# Configuration
API_URL = os.getenv("API_URL", "https://store-intelligence-api.onrender.com")
DEFAULT_STORE = "STORE_BLR_002"
WAKE_UP_TIMEOUT = 120  # seconds to wait for API to wake up

# Page config
st.set_page_config(
    page_title="Store Intelligence Dashboard",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Wake-up gate ────────────────────────────────────────────────────────────────
def _is_api_alive() -> bool:
    """Return True if the API responds with 200."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=8)
        return r.status_code == 200
    except Exception:
        return False

def wake_up_api():
    """
    Block in a loading screen until the API is alive.
    Returns immediately if the API is already up.
    Render free-tier services spin down after inactivity; this pings them
    awake so the user never has to open the API URL manually.
    """
    if _is_api_alive():
        return  # already up – no loading screen needed

    # Show loading UI
    st.markdown("""
    <style>
        .wake-title  { font-size:2rem; font-weight:700; text-align:center; margin-top:3rem; }
        .wake-sub    { font-size:1.1rem; color:#666; text-align:center; margin-bottom:2rem; }
        .wake-note   { font-size:0.85rem; color:#999; text-align:center; }
    </style>
    <div class="wake-title">🏪 Store Intelligence</div>
    <div class="wake-sub">Waking up the API — this takes about 30–60 seconds on first load.</div>
    <div class="wake-note">Render free tier spins down idle services. Hang tight!</div>
    """, unsafe_allow_html=True)

    progress_bar = st.progress(0, text="Connecting to API…")
    status_text  = st.empty()

    deadline = time.time() + WAKE_UP_TIMEOUT
    attempt  = 0

    while time.time() < deadline:
        attempt += 1
        elapsed  = WAKE_UP_TIMEOUT - (deadline - time.time())
        pct      = min(int(elapsed / WAKE_UP_TIMEOUT * 100), 95)

        status_text.markdown(
            f"<p style='text-align:center;color:#555;'>Attempt {attempt} — "
            f"elapsed {int(elapsed)}s / {WAKE_UP_TIMEOUT}s…</p>",
            unsafe_allow_html=True,
        )
        progress_bar.progress(pct, text=f"Waiting for API… ({int(elapsed)}s)")

        if _is_api_alive():
            progress_bar.progress(100, text="✅ API is live!")
            status_text.markdown(
                "<p style='text-align:center;color:green;font-weight:600;'>"
                "API is up! Loading dashboard…</p>",
                unsafe_allow_html=True,
            )
            time.sleep(0.8)
            st.rerun()

        time.sleep(4)  # poll every 4 seconds

    # Timed out
    progress_bar.progress(100, text="⚠️ Timed out")
    st.error(
        f"Could not reach the API at `{API_URL}` within {WAKE_UP_TIMEOUT}s. "
        "Try refreshing the page, or check the Render dashboard."
    )
    st.stop()

# Run the wake-up gate before anything else
wake_up_api()
# ────────────────────────────────────────────────────────────────────────────────

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
@st.cache_data(ttl=30)
def fetch_health():
    """Fetch system health."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_metrics(store_id, date=None):
    """Fetch store metrics."""
    try:
        url = f"{API_URL}/stores/{store_id}/metrics"
        if date:
            url += f"?date={date}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_heatmap(store_id, date=None):
    """Fetch zone heatmap."""
    try:
        url = f"{API_URL}/stores/{store_id}/heatmap"
        if date:
            url += f"?date={date}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_funnel(store_id, date=None):
    """Fetch conversion funnel."""
    try:
        url = f"{API_URL}/stores/{store_id}/funnel"
        if date:
            url += f"?date={date}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_anomalies(store_id):
    """Fetch active anomalies."""
    try:
        response = requests.get(f"{API_URL}/stores/{store_id}/anomalies", timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

# Main app
def main():
    # Header
    st.markdown('<div class="main-header">🏪 Store Intelligence Dashboard</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Check health
        health = fetch_health()
        if health:
            status = health.get("status", "unknown")
            status_color = {
                "healthy": "🟢",
                "degraded": "🟡",
                "unhealthy": "🔴"
            }.get(status, "⚪")
            st.metric("System Status", f"{status_color} {status.upper()}")
            
            # Store selection
            stores = health.get("stores", [])
            if stores:
                store_options = [s["store_id"] for s in stores]
                selected_store = st.selectbox("Select Store", store_options, index=0)
            else:
                selected_store = st.text_input("Store ID", DEFAULT_STORE)
        else:
            st.error("❌ Cannot connect to API")
            selected_store = st.text_input("Store ID", DEFAULT_STORE)
        
        # Date selection
        st.subheader("📅 Date Range")
        selected_date = st.date_input(
            "Select Date",
            value=datetime(2026, 5, 31),  # Default to May 31, 2026
            min_value=datetime(2026, 1, 1),
            max_value=datetime.now()
        )
        
        # Auto-refresh
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
        if auto_refresh:
            st.info("Dashboard will refresh every 30 seconds")
        
        st.divider()
        st.caption(f"API: {API_URL}")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
    
    # Main content
    # The wake_up_api() gate above already confirmed the API is live,
    # but we still handle the (rare) case where it goes down mid-session.
    if not health:
        st.error("🔴 Lost connection to the API. Please refresh the page.")
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()
        return
    
    # Fetch data
    date_str = selected_date.strftime("%Y-%m-%d")
    metrics = fetch_metrics(selected_store, date_str)
    heatmap_data = fetch_heatmap(selected_store, date_str)
    funnel_data = fetch_funnel(selected_store, date_str)
    anomalies = fetch_anomalies(selected_store)
    
    # Display anomalies if any
    if anomalies:
        # Handle both dict and list responses
        anomaly_list = anomalies.get("anomalies", []) if isinstance(anomalies, dict) else anomalies
        
        if anomaly_list:
            st.warning(f"⚠️ {len(anomaly_list)} Active Anomalies")
            with st.expander("View Anomalies"):
                for anomaly in anomaly_list:
                    severity_icon = {"INFO": "ℹ️", "WARN": "⚠️", "CRITICAL": "🚨"}.get(anomaly.get("severity", ""), "•")
                    st.markdown(f"**{severity_icon} {anomaly.get('description', 'Unknown anomaly')}**")
                    st.caption(f"→ {anomaly.get('suggested_action', 'No action suggested')}")
    
    # Metrics Overview
    st.header("📊 Key Metrics")
    
    if metrics:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "👥 Unique Visitors",
                metrics.get("unique_visitors", 0),
                help="Total unique visitors detected"
            )
        
        with col2:
            st.metric(
                "🚪 Entries",
                metrics.get("total_entries", 0),
                help="Total store entries"
            )
        
        with col3:
            st.metric(
                "🛒 Conversion Rate",
                f"{metrics.get('conversion_rate', 0) * 100:.1f}%",
                help="Percentage of visitors who made a purchase"
            )
        
        with col4:
            st.metric(
                "👔 Staff Excluded",
                metrics.get("staff_excluded", 0),
                help="Staff members filtered from analytics"
            )
        
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            st.metric(
                "🚶 Exits",
                metrics.get("total_exits", 0),
                help="Total store exits"
            )
        
        with col6:
            st.metric(
                "⏱️ Queue Depth",
                metrics.get("current_queue_depth", 0),
                help="Current billing queue depth"
            )
        
        with col7:
            st.metric(
                "🚫 Abandonment Rate",
                f"{metrics.get('abandonment_rate', 0) * 100:.1f}%",
                help="Percentage of visitors who left queue"
            )
        
        with col8:
            st.metric(
                "📅 Date",
                date_str,
                help="Selected date for analytics"
            )
    else:
        st.info(f"ℹ️ No metrics available for {date_str}")
    
    st.divider()
    
    # Zone Analytics
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.header("🗺️ Zone Heatmap")
        
        if heatmap_data:
            # Handle both dict and list responses
            if isinstance(heatmap_data, dict) and heatmap_data.get("zones"):
                zones = heatmap_data["zones"]
            elif isinstance(heatmap_data, list):
                zones = heatmap_data
            else:
                zones = []
            
            if zones:
                zones_df = pd.DataFrame([
                    {"Zone": zone["zone_id"], "Visits": zone["visit_count"], "Avg Dwell (s)": zone["avg_dwell_ms"]/1000}
                    for zone in zones
                ])
            
                # Bar chart for visits
                fig_visits = px.bar(
                    zones_df,
                    x="Zone",
                    y="Visits",
                    title="Zone Visit Count",
                    color="Visits",
                    color_continuous_scale="Blues"
                )
                fig_visits.update_layout(showlegend=False)
                st.plotly_chart(fig_visits, use_container_width=True)
                
                # Display table
                st.dataframe(zones_df, use_container_width=True, hide_index=True)
            else:
                st.info("No zone data available for this date")
        else:
            st.info("No zone data available")
    
    with col_right:
        st.header("⏱️ Dwell Time Analysis")
        
        if metrics and metrics.get("avg_dwell_per_zone"):
            dwell_df = pd.DataFrame([
                {"Zone": zone, "Avg Dwell (ms)": dwell, "Avg Dwell (s)": dwell/1000}
                for zone, dwell in metrics["avg_dwell_per_zone"].items()
            ]).sort_values("Avg Dwell (ms)", ascending=False)
            
            # Bar chart for dwell time
            fig_dwell = px.bar(
                dwell_df,
                x="Zone",
                y="Avg Dwell (s)",
                title="Average Dwell Time by Zone",
                color="Avg Dwell (s)",
                color_continuous_scale="Greens"
            )
            fig_dwell.update_layout(showlegend=False)
            st.plotly_chart(fig_dwell, use_container_width=True)
            
            # Display table
            st.dataframe(dwell_df[["Zone", "Avg Dwell (s)"]], use_container_width=True, hide_index=True)
        else:
            st.info("No dwell time data available")
    
    st.divider()
    
    # Conversion Funnel
    st.header("🔄 Conversion Funnel")
    
    if funnel_data:
        # Handle both dict and list responses
        if isinstance(funnel_data, dict) and funnel_data.get("stages"):
            stages = funnel_data["stages"]
        elif isinstance(funnel_data, list):
            stages = funnel_data
        else:
            stages = []
            
        if stages:
            stages_df = pd.DataFrame(stages)
        
            # Funnel chart
            fig_funnel = go.Figure(go.Funnel(
                y=stages_df["stage"],
                x=stages_df["count"],
                textinfo="value+percent initial",
                marker={"color": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]}
            ))
            fig_funnel.update_layout(title="Customer Journey Funnel", height=400)
            st.plotly_chart(fig_funnel, use_container_width=True)
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                entry_to_browse = funnel_data.get('entry_to_browse_rate', 0) if isinstance(funnel_data, dict) else 0
                st.metric("Entry → Browse", f"{entry_to_browse*100:.1f}%")
            with col2:
                browse_to_queue = funnel_data.get('browse_to_queue_rate', 0) if isinstance(funnel_data, dict) else 0
                st.metric("Browse → Queue", f"{browse_to_queue*100:.1f}%")
            with col3:
                queue_to_purchase = funnel_data.get('queue_to_purchase_rate', 0) if isinstance(funnel_data, dict) else 0
                st.metric("Queue → Purchase", f"{queue_to_purchase*100:.1f}%")
        else:
            st.info("No funnel data available for this date")
    else:
        st.info("No funnel data available")
    
    # Auto-refresh
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
