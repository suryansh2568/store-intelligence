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

# Configuration
API_URL = os.getenv("API_URL", "http://api:8000")
# For production, use: API_URL = os.getenv("API_URL", "https://your-api.railway.app")
DEFAULT_STORE = "STORE_BLR_002"

# Page config
st.set_page_config(
    page_title="Store Intelligence Dashboard",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_metrics(store_id, date=None):
    """Fetch store metrics."""
    try:
        url = f"{API_URL}/stores/{store_id}/metrics"
        if date:
            url += f"?date={date}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_heatmap(store_id, date=None):
    """Fetch zone heatmap."""
    try:
        url = f"{API_URL}/stores/{store_id}/heatmap"
        if date:
            url += f"?date={date}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        # Log error but don't show to user unless in debug mode
        pass
    return None

@st.cache_data(ttl=30)
def fetch_funnel(store_id, date=None):
    """Fetch conversion funnel."""
    try:
        url = f"{API_URL}/stores/{store_id}/funnel"
        if date:
            url += f"?date={date}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

@st.cache_data(ttl=30)
def fetch_anomalies(store_id):
    """Fetch active anomalies."""
    try:
        response = requests.get(f"{API_URL}/stores/{store_id}/anomalies", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
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
    if not health:
        st.error("🔴 Cannot connect to API. Please check if the API service is running.")
        st.code(f"API URL: {API_URL}")
        st.info("Try: docker-compose restart api")
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
        st.info("No funnel data available")
    
    # Auto-refresh
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
