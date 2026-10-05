from app.rag import LLMService, SimpleRetrievalStrategy
from app.storage.vector_db.qdrant import QdrantService
from app.storage.postgres import PostgresDatabase
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
    
    return qdrant, llm

try:
    qdrant_service, llm_service = init_services()
except Exception as e:
    st.error(f"Failed to initialize services: {e}")
    st.info("Check your Qdrant URL/API Key in Streamlit Secrets.")
    st.stop()

# --- Cached Data Fetching ---
@st.cache_data(ttl=3600)
def fetch_analytics():
    try:
        db = PostgresDatabase()
        try:
            return db.get_category_stats()
        finally:
            db.close()
    except Exception as e:
        st.warning(f"Could not fetch analytics from Postgres: {e}")
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
