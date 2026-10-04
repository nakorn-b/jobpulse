from app.rag import LLMService, SimpleRetrievalStrategy
from app.storage.vector_db.qdrant import QdrantService
from app.storage.bigquery import BigQueryService
import streamlit as st
from streamlit_echarts import st_echarts
import os
import json

# --- Configuration & Secrets ---
# Streamlit Cloud automatically maps Secrets to Environment Variables
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_ENDPOINT = os.getenv('QDRANT_CLUSTER_ENDPOINT')
# Default to False (Cloud Mode) unless explicitly set to 'true'
QDRANT_LOCAL_MODE = os.getenv('QDRANT_LOCAL_MODE', 'False').lower() == 'true'

# Initialize Services
@st.cache_resource
def init_services():
    # Validation
    if not QDRANT_LOCAL_MODE and not QDRANT_ENDPOINT:
        st.error("Missing QDRANT_CLUSTER_ENDPOINT! Please add it to Streamlit Secrets.")
        st.stop()
        
    qdrant = QdrantService(
        API_KEY=QDRANT_API_KEY, 
        url=QDRANT_ENDPOINT or 'http://localhost:6333', 
        local=QDRANT_LOCAL_MODE
    )
    strategy = SimpleRetrievalStrategy()
    llm = LLMService(qdrant, strategy)
    
    GCP_PROJECT = "jobpulse-492611"
    
    GCP_SA_KEYS = ["type", "project_id", "private_key_id", "private_key",
                    "client_email", "client_id", "auth_uri", "token_uri",
                    "auth_provider_x509_cert_url", "client_x509_cert_url"]
    
    class BQHook:
        def get_client(self):
            from google.cloud import bigquery
            
            # 1. Try nested [gcp_service_account] section in Streamlit Secrets
            if "gcp_service_account" in st.secrets:
                info = dict(st.secrets["gcp_service_account"])
                return bigquery.Client.from_service_account_info(info, project=GCP_PROJECT)
            
            # 2. Try flat top-level GCP keys in Streamlit Secrets
            if "type" in st.secrets and "private_key" in st.secrets:
                info = {k: st.secrets[k] for k in GCP_SA_KEYS if k in st.secrets}
                if "universe_domain" in st.secrets:
                    info["universe_domain"] = st.secrets["universe_domain"]
                return bigquery.Client.from_service_account_info(info, project=GCP_PROJECT)
            
            # 3. Try local file (For local development)
            if os.path.exists("gcp-key.json"):
                return bigquery.Client.from_service_account_json("gcp-key.json", project=GCP_PROJECT)
            
            # 4. No credentials found
            raise RuntimeError(
                "No GCP credentials found. "
                "Add GCP service account keys to Streamlit Secrets, "
                "or place a gcp-key.json file in the project root for local dev."
            )
    
    bq_service = BigQueryService(BQHook())
    return qdrant, llm, bq_service

try:
    qdrant_service, llm_service, bq_service = init_services()
except Exception as e:
    st.error(f"Failed to initialize services: {e}")
    st.info("Check your Qdrant URL/API Key and GCP service account in Streamlit Secrets.")
    st.stop()

# --- Cached Data Fetching ---
@st.cache_data(ttl=3600)
def fetch_analytics():
    try:
        return bq_service.get_category_stats()
    except Exception as e:
        st.warning(f"Could not fetch analytics from BigQuery: {e}")
        return []

@st.cache_data(ttl=600)
def get_total_count():
    try:
        stats = qdrant_service.get_stats()
        return stats.get("total_points", 0)
    except:
        return 0

data_count = get_total_count()

# --- UI Layout ---
st.set_page_config(page_title="JobPulse", page_icon="🚀", layout="wide")

st.title("JobPulse", anchor=False)

# Create Tabs
tab_chat, tab_insights = st.tabs(["💬 Job Assistant", "📊 Market Insights"])

with tab_chat:
    st.caption(f"🚀 Connected to Qdrant Cloud | {data_count} jobs indexed")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    has_message_history = len(st.session_state.messages) > 0

    SUGGESTIONS = {
        "Find me AI Engineer jobs": ":material/smart_toy: AI Engineer",
        "Find me Data Engineer jobs": ":material/storage: Data Engineer",
        "Find me Software Engineer jobs": ":material/code: Software Engineer",
        "Find me Machine Learning Engineer jobs": ":material/model_training: ML Engineer",
    }

    if not has_message_history:
        selection = st.pills("Suggested Searches", list(SUGGESTIONS.keys()), format_func=lambda x: SUGGESTIONS[x] )
        if selection:
            st.session_state.messages.append({"role": "user", "content": selection})
            with st.spinner("Searching..."):
                response  = llm_service.query(selection)
            st.session_state.messages.append({"role": "ai", "content": response})
            st.rerun()

    # Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask about jobs..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Searching Qdrant..."):
            response  = llm_service.query(prompt)
        st.session_state.messages.append({"role": "ai", "content": response})
        st.rerun()

with tab_insights:
    st.subheader("Live Market Composition")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("Total Jobs Indexed", data_count)
        cat_data = fetch_analytics()
        if cat_data:
            top_cat = cat_data[0]['name']
            st.info(f"🔥 **{top_cat}** is currently the most active category.")

    with col2:
        if cat_data:
            options = {
                "tooltip": {"trigger": "item"},
                "legend": {"top": "5%", "left": "center"},
                "series": [
                    {
                        "name": "Job Categories",
                        "type": "pie",
                        "radius": ["40%", "70%"],
                        "avoidLabelOverlap": False,
                        "itemStyle": {
                            "borderRadius": 10,
                            "borderColor": "#fff",
                            "borderWidth": 2,
                        },
                        "label": {"show": False, "position": "center"},
                        "emphasis": {
                            "label": {"show": True, "fontSize": "20", "fontWeight": "bold"}
                        },
                        "labelLine": {"show": False},
                        "data": cat_data,
                    }
                ],
            }
            st_echarts(options=options, height="500px")
        else:
            st.info("Analytics data is currently unavailable.")
