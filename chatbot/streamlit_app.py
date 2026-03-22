import sys
import pathlib
import streamlit as st
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chatbot.rag_engine import SmartRAG

# Page config
st.set_page_config(
    page_title="YCCE Smart Chatbot",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(1200px 600px at 5% 0%, rgba(8, 145, 178, 0.08), transparent 40%),
            radial-gradient(1000px 500px at 95% 0%, rgba(16, 185, 129, 0.08), transparent 45%),
            linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    }
    .ycce-hero {
        border: 1px solid rgba(15, 23, 42, 0.08);
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(4px);
        border-radius: 16px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .ycce-hero h1 {
        margin: 0;
        font-size: 1.35rem;
        color: #0f172a;
        letter-spacing: 0.2px;
    }
    .ycce-hero p {
        margin: 4px 0 0 0;
        color: #334155;
        font-size: 0.95rem;
    }
    .ycce-pill {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 999px;
        border: 1px solid rgba(15, 23, 42, 0.1);
        background: rgba(255, 255, 255, 0.9);
        color: #0f172a;
        font-size: 0.78rem;
        margin-right: 8px;
        margin-top: 8px;
    }
    .stChatMessage {
        border-radius: 14px;
    }
    .stChatMessage [data-testid="stMarkdownContainer"] p {
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="ycce-hero">
      <h1>YCCE Smart Chatbot</h1>
      <p>Ask naturally. Get focused answers grounded in your YCCE knowledge base.</p>
      <span class="ycce-pill">RAG + Groq LLM</span>
      <span class="ycce-pill">Multi-Query Retrieval</span>
      <span class="ycce-pill">Concise Answer Mode</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.caption("Yogi Chiranji Lal College of Engineering Smart Assistant")
    st.caption("Uses advanced retrieval-augmented generation with Groq LLM")
    st.divider()
    st.markdown("**Note**: Answers now include evidence-based explanation and relevant links.")
    # remove checkbox options to present final answer only
    show_sources = False
    show_metrics = False

    if st.button("🧹 New Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    st.divider()
    st.markdown("**About**")
    st.caption("Designed for concise, user-friendly responses")

# Initialize RAG engine in session state
if "rag" not in st.session_state:
    st.session_state.rag = SmartRAG()

# Chat history in session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for message in st.session_state.chat_history:
    role = "assistant" if message["role"] == "bot" else "user"
    avatar = "🎓" if role == "assistant" else "🧑"
    with st.chat_message(role, avatar=avatar):
        st.markdown(message["content"])


def stream_text(text: str):
    """Lightweight token streaming for assistant responses."""
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(0.01)

query = st.chat_input("Ask about YCCE admissions, departments, academics, placements...")

# Process query
if query and query.strip():
    # Add user query to history
    st.session_state.chat_history.append({
        "role": "user",
        "content": query
    })
    with st.chat_message("user", avatar="🧑"):
        st.markdown(query)
    
    # Generate response
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("Searching relevant documents and drafting answer..."):
            result = st.session_state.rag.answer(query)

        answer_text = result["answer"]
        st.write_stream(stream_text(answer_text))

    # Add bot response to history
    st.session_state.chat_history.append({
        "role": "bot",
        "content": answer_text,
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", 0.0),
        "docs_count": result.get("docs_count", 0)
    })

    # Rerun for stable widget state
    st.rerun()

# Footer
if st.session_state.chat_history:
    st.divider()
    st.caption(
        f"💬 {len([m for m in st.session_state.chat_history if m['role'] == 'user'])} questions asked in this chat"
    )