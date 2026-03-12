import os
from typing import List

from langchain_community.vectorstores import FAISS
from config import FAISS_PATH

try:
    from langchain.embeddings import HuggingFaceEmbeddings
except Exception:
    HuggingFaceEmbeddings = None


class SentenceTransformerWrapper:
    """Minimal wrapper providing `embed_documents` and `embed_query` using
    `sentence_transformers.SentenceTransformer` so FAISS can use it in place
    of LangChain's HuggingFaceEmbeddings.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise ImportError(
                "sentence-transformers is required for the fallback embeddings. "
                "Install it with `pip install sentence-transformers`"
            ) from e
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=False)
        if hasattr(vectors, "tolist"):
            return vectors.tolist()
        return [list(v) for v in vectors]

    def embed_query(self, text: str) -> List[float]:
        vector = self.model.encode([text], show_progress_bar=False, convert_to_numpy=False)[0]
        if hasattr(vector, "tolist"):
            return vector.tolist()
        return list(vector)

    def __call__(self, text: str) -> List[float]:
        # Compatibility with call-sites expecting a callable embedding function.
        return self.embed_query(text)


if HuggingFaceEmbeddings is not None:
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
else:
    # Fallback to sentence-transformers directly to avoid hard dependency on
    # langchain-huggingface while still producing embeddings.
    embeddings = SentenceTransformerWrapper("sentence-transformers/all-MiniLM-L6-v2")


def upsert_documents(documents):
    if os.path.exists(FAISS_PATH):
        db = FAISS.load_local(
            FAISS_PATH,
            embeddings,
            allow_dangerous_deserialization=True
        )
        db.add_documents(documents)
    else:
        db = FAISS.from_documents(documents, embeddings)

    db.save_local(FAISS_PATH)