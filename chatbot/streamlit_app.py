import sys
import pathlib
import streamlit as st

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chatbot.rag_engine import SmartRAG

# Page config
st.set_page_config(
    page_title="YCCE Smart Chatbot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎓 YCCE Smart Chatbot")
st.markdown("*Powered by RAG + Groq LLM | Multi-Query Retrieval | 7+ Context Documents*")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.caption("Yogi Chiranji Lal College of Engineering Smart Assistant")
    st.caption("Uses advanced retrieval-augmented generation with Groq LLM")
    st.divider()
    st.markdown("**Note**: Sources and metrics are hidden for a cleaner chatbot experience.")
    # remove checkbox options to present final answer only
    show_sources = False
    show_metrics = False
    
    st.divider()
    st.markdown("**About**")
    st.caption("Designed for concise, user-friendly responses")

# Initialize RAG engine in session state
if "rag" not in st.session_state:
    st.session_state.rag = SmartRAG()

# Chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display chat history
st.subheader("💬 Conversation")
chat_container = st.container()

with chat_container:
    for i, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            st.markdown(f"**You:** {message['content']}")
        else:
            st.markdown(f"**Bot:** {message['content']}")
            # sources and metrics intentionally omitted for clean display


# Input section
st.divider()
col1, col2 = st.columns([5, 1])

with col1:
    query = st.text_input(
        "Ask about YCCE...",
        placeholder="e.g., What are admission requirements? Tell me about BTech CSE curriculum?"
    )

with col2:
    submit_button = st.button("Send", use_container_width=True, type="primary")

# Process query
if submit_button and query.strip():
    # Add user query to history
    st.session_state.chat_history.append({
        "role": "user",
        "content": query
    })
    
    # Generate response
    with st.spinner("🔍 Searching database... 🤖 Generating answer..."):
        result = st.session_state.rag.answer(query)
        
        # Add bot response to history
        st.session_state.chat_history.append({
            "role": "bot",
            "content": result["answer"],
            "sources": result.get("sources", []),
            "confidence": result.get("confidence", 0.0),
            "docs_count": result.get("docs_count", 0)
        })
    
    # Rerun to display new messages
    st.rerun()

# Footer
if st.session_state.chat_history:
    st.divider()
    st.caption(f"📊 Conversation History: {len([m for m in st.session_state.chat_history if m['role'] == 'user'])} questions asked")