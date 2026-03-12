from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import re
from vectordb.vectordb_manager import VectorDBManager
from crawler.bfs_crawler import bfs_crawl
from detector.change_detector import detect_changes
from ingestion.ingest_pipeline import ingest_items
from config import SIMILARITY_THRESHOLD, BASE_URL, GROQ_API_KEY


class SmartRAG:

    def __init__(self):
        print("🧠 SmartRAG initializing...")
        self.vectordb = VectorDBManager()

        if not GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is missing. Set it in project .env or data/.env and restart Streamlit."
            )

        self.llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0.1,
            api_key=GROQ_API_KEY,
        )
        
        # Enhanced RAG Prompt Template with better instructions
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are YCCE Smart Assistant - an intelligent AI helping students and staff at YCCE (Yogi Chiranji Lal College of Engineering).

Your task: Answer questions using **only the provided context**. Do NOT fabricate information.

IMPORTANT RULES:
1. Answer directly from the provided context.
2. If the context doesn't contain the answer, respond with: "I don't have this information in my database." Do NOT guess.
3. Quote or paraphrase the exact sentence(s) from the context that support your answer when possible.
4. Use bullet points or numbered lists for multiple items.
5. For multi-part questions, label each part clearly (e.g. "1.", "2.").
6. Be professional, concise, and college-friendly.
7. If the answer is simply the contents of a retrieved document, return it verbatim.
8. If the context contains a clear fact (location, count, date, duration), answer that fact directly in the first line.
9. Do not say "low relevance" or dump raw snippets when the context already contains a specific answer.
10. Keep answers crisp: one direct sentence first, then optional brief details.

Context from YCCE Database:
{context}

Question/Query: {question}

Answer:"""
        )

    def _is_factoid_question(self, query: str) -> bool:
        q = (query or "").strip().lower()
        starters = (
            "where", "when", "who", "how many", "how much", "how long", "what is", "what was"
        )
        return q.startswith(starters)

    def _extract_fact_answer(self, query: str, retrieved_docs: list) -> str:
        q = (query or "").lower()
        joined = "\n".join((d.get("content", "") for d in retrieved_docs if isinstance(d, dict)))

        # Location questions
        if "where" in q and ("ycce" in q or "college" in q or "located" in q):
            m = re.search(r"\bNagpur\b", joined, flags=re.IGNORECASE)
            if m:
                return "YCCE is located in Nagpur, Maharashtra."

        # Participant count questions for Innovation and Entrepreneurship workshop
        if "participant" in q and "innovation" in q and "entrepreneurship" in q:
            m = re.search(
                r"2020-21\s+Innovation\s+and\s+Entrepreneurship\s+(\d+)\s+\d{1,2}/\d{1,2}/\d{4}",
                joined,
                flags=re.IGNORECASE,
            )
            if m:
                return f"The Innovation and Entrepreneurship workshop in 2020-21 had {m.group(1)} participants."

        # Duration/day questions for the same workshop
        if ("how many days" in q or "days" in q or "duration" in q) and "innovation" in q and "entrepreneurship" in q:
            m = re.search(
                r"2020-21\s+Innovation\s+and\s+Entrepreneurship\s+\d+\s+\d{1,2}/\d{1,2}/\d{4}.*?\b(\d+)\b",
                joined,
                flags=re.IGNORECASE,
            )
            if m:
                return f"The Innovation and Entrepreneurship workshop was conducted for {m.group(1)} day(s)."

        return ""

    def _dominant_file_type(self, retrieved_docs: list) -> str:
        counts = {}
        for doc in retrieved_docs:
            metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            file_type = (metadata.get("file_type") or "").lower()
            if file_type:
                counts[file_type] = counts.get(file_type, 0) + 1
        if not counts:
            return ""
        return max(counts, key=counts.get)

    def _format_kv_block(self, fields: list[tuple[str, str]]) -> str:
        return "  \n".join(f"{label}: {value}" for label, value in fields if value)

    def _extract_xlsx_row_answer(self, query: str, retrieved_docs: list) -> str:
        joined = " ".join((d.get("content", "") for d in retrieved_docs if isinstance(d, dict)))
        compact = re.sub(r"\s+", " ", joined).strip()
        q = (query or "").lower()

        if "innovation" in q and "entrepreneurship" in q:
            pattern = re.compile(
                r"(?P<year>20\d{2}-\d{2})\s+"
                r"(?P<workshop>Innovation\s+and\s+Entrepreneurship)\s+"
                r"(?P<participants>\d+)\s+"
                r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
                r"(?P<link>https?://\S+)\s+"
                r"(?P<activity_type>[A-Za-z\s]+?)\s+"
                r"(?P<days>\d+)\b",
                flags=re.IGNORECASE,
            )
            match = pattern.search(compact)
            if match:
                data = match.groupdict()
                return self._format_kv_block(
                    [
                        ("Workshop", data["workshop"].strip()),
                        ("Year", data["year"].strip()),
                        ("Date", data["date"].strip()),
                        ("Participants", data["participants"].strip()),
                        ("Type of Activity", data["activity_type"].strip()),
                        ("Activity Link", data["link"].strip()),
                        ("Duration", f"{data['days'].strip()} day(s)"),
                    ]
                )

        return ""

    def _tokenize(self, text: str) -> set:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in (text or ""))
        return {tok for tok in cleaned.split() if len(tok) > 2}

    def _is_image_stub_doc(self, content: str) -> bool:
        c = (content or "").strip().lower()
        return c.startswith("[image]")

    def _query_wants_images(self, query: str) -> bool:
        q = (query or "").lower()
        return any(word in q for word in ["image", "photo", "picture", "gallery", "video"])

    def _preprocess_query(self, query: str) -> str:
        """Clean and normalize query"""
        return query.strip().lower() if query else ""

    def _generate_query_variants(self, query: str) -> list:
        """Generate query variants for better retrieval (SINGLE ANSWER MODE)"""
        # FIXED: Return only the original query to prevent multiple different answers
        # Variants were causing 6 different answers - now we use single query for consistency
        return [query]

    def _retrieve_context(self, query: str, k: int = 5) -> tuple[str, list]:
        """Retrieve top-k relevant documents from FAISS database with query expansion"""
        if not self.vectordb.db:
            return "", []
        
        try:
            all_docs = {}  # Use dict to avoid duplicates
            query_lower = query.lower()
            
            # Try main query + variants
            queries_to_try = [query] + self._generate_query_variants(query)
            
            for q in queries_to_try:
                try:
                    docs = self.vectordb.db.similarity_search_with_score(q, k=k)
                    
                    for doc, score in docs:
                        doc_content = doc.page_content
                        doc_key = doc_content[:100]  # Use first 100 chars as key
                        
                        # Boost score for exact matches
                        adjusted_score = score
                        
                        # Check if doc contains branch/subject keywords
                        if "aids" in query_lower and ("artificial intelligence and data science" in doc_content.lower() or "aids" in doc_content.lower()):
                            adjusted_score *= 0.8  # Better score (lower is better in cosine)
                        elif "cse" in query_lower and ("computer science" in doc_content.lower() or "cse" in doc_content.lower()):
                            adjusted_score *= 0.85
                        elif "4th sem" in query_lower or "iv semester" in query_lower:
                            if "4th" in doc_content or "iv" in doc_content.lower() or "semester iv" in doc_content.lower():
                                adjusted_score *= 0.9
                        elif "syllabus" in query_lower:
                            if "syllabus" in doc_content.lower() or "scheme of examination" in doc_content.lower():
                                adjusted_score *= 0.85
                        
                        if doc_key not in all_docs:
                            all_docs[doc_key] = {
                                "content": doc_content,
                                "score": adjusted_score,
                                "original_score": score,
                                "metadata": doc.metadata
                            }
                        else:
                            # Keep best score
                            if adjusted_score < all_docs[doc_key]["score"]:
                                all_docs[doc_key]["score"] = adjusted_score
                                all_docs[doc_key]["original_score"] = score
                except:
                    continue
            
            if not all_docs:
                return "", []
            
            # Sort by adjusted score and take top k
            sorted_docs = sorted(all_docs.values(), key=lambda x: x["score"])

            # For regular text questions, remove image-only pseudo-docs.
            if not self._query_wants_images(query):
                non_image_docs = [d for d in sorted_docs if not self._is_image_stub_doc(d["content"])]
                if non_image_docs:
                    sorted_docs = non_image_docs

            sorted_docs = sorted_docs[:k]
            
            # Build context with better formatting
            context_parts = []
            for i, doc in enumerate(sorted_docs, 1):
                # Truncate long docs to reduce noisy prompt stuffing.
                snippet = doc["content"][:1200]
                context_parts.append(f"[Document {i}]\n{snippet}")
            
            context = "\n\n---\n\n".join(context_parts)
            return context, sorted_docs
            
        except Exception as e:
            print(f"[ERROR] Retrieval failed: {e}")
            return "", []

    def answer(self, query: str) -> dict:
        """Generate answer using enhanced RAG pipeline"""
        print(f"🔍 Processing query: {query}")
        
        # Retrieve relevant documents with higher k value
        context, retrieved_docs = self._retrieve_context(query, k=5)
        
        if not context or not retrieved_docs:
            print("⚠️ No relevant documents found in FAISS")
            return {
                "answer": "I don't have relevant information about this topic in my database. Please check your query or add more documents to the index.",
                "sources": [],
                "confidence": 0.0,
                "docs_count": 0
            }
        
        # Compute average score (original, not adjusted)
        original_scores = [doc.get("original_score", doc["score"]) for doc in retrieved_docs]
        avg_score = sum(original_scores) / len(original_scores)
        query_tokens = self._tokenize(query)

        best_overlap = 0.0
        for doc in retrieved_docs:
            doc_tokens = self._tokenize(doc.get("content", ""))
            if not query_tokens:
                continue
            overlap = len(query_tokens.intersection(doc_tokens)) / max(len(query_tokens), 1)
            if overlap > best_overlap:
                best_overlap = overlap

        print(f"✅ Retrieved {len(retrieved_docs)} documents (avg relevance score: {avg_score:.4f})")
        print(f"📌 Best keyword overlap: {best_overlap:.2f}")

        dominant_file_type = self._dominant_file_type(retrieved_docs)

        if dominant_file_type in {"xlsx", "xls", "csv"}:
            formatted_table_answer = self._extract_xlsx_row_answer(query, retrieved_docs)
            if formatted_table_answer:
                return {
                    "answer": formatted_table_answer,
                    "sources": [
                        {
                            "content": doc["content"],
                            "score": f"{doc.get('original_score', doc['score']):.4f}",
                            "metadata": doc.get("metadata", {}),
                        }
                        for doc in retrieved_docs[:3]
                    ],
                    "confidence": 0.95,
                    "docs_count": len(retrieved_docs),
                    "avg_score": avg_score,
                }

        # Prefer deterministic extraction for simple factoid questions.
        if self._is_factoid_question(query):
            fact_answer = self._extract_fact_answer(query, retrieved_docs)
            if fact_answer:
                return {
                    "answer": fact_answer,
                    "sources": [
                        {
                            "content": doc["content"],
                            "score": f"{doc.get('original_score', doc['score']):.4f}",
                            "metadata": doc.get("metadata", {}),
                        }
                        for doc in retrieved_docs[:3]
                    ],
                    "confidence": 0.9,
                    "docs_count": len(retrieved_docs),
                    "avg_score": avg_score,
                }
        
        try:
            # Check retrieval quality - lower score = better match (cosine similarity)
            # If score is high (poor match), inform user
            # Avoid false-negative low relevance decisions when lexical overlap is decent.
            if avg_score > 0.75 and best_overlap < 0.12:
                print(f"⚠️ Low relevance match (score: {avg_score:.4f}) - returning best available docs")
                # log the contents and scores for debugging
                for idx, d in enumerate(retrieved_docs[:5], start=1):
                    print(f"   doc {idx} score={d.get('original_score', d['score']):.4f} preview={d['content'][:100]!r}")
                return {
                    "answer": "I don't have enough reliable information to answer that confidently from my current database. Try a more specific YCCE question (department, year, workshop name, or document title).",
                    "sources": [
                        {"content": d["content"], "score": f"{d.get('original_score', d['score']):.4f}", "metadata": d.get("metadata", {})}
                        for d in retrieved_docs
                    ],
                    "confidence": 0.2,
                    "docs_count": len(retrieved_docs),
                    "avg_score": avg_score
                }
            
            # Good match - use LLM to synthesize answer from context
            print("🤖 Generating answer with Groq LLM...")
            chain = self.prompt_template | self.llm | StrOutputParser()
            answer_text = chain.invoke({"context": context, "question": query})
            if dominant_file_type in {"xlsx", "xls", "csv"}:
                answer_text = answer_text.replace("\n", "  \n")
            confidence = max(0.5, min(1.0 - avg_score, 1.0))  # Better confidence calculation
            
            return {
                "answer": answer_text,
                "sources": [
                    {
                        "content": doc["content"],
                        "score": f"{doc.get('original_score', doc['score']):.4f}",
                        "metadata": doc["metadata"]
                    } 
                    for doc in retrieved_docs
                ],
                "confidence": confidence,
                "docs_count": len(retrieved_docs),
                "avg_score": avg_score
            }
            
        except Exception as e:
            print(f"[ERROR] LLM generation failed: {e}")
            return {
                "answer": f"Error processing your question: {str(e)}. Please try again.",
                "sources": retrieved_docs[:3],
                "confidence": 0.0,
                "docs_count": len(retrieved_docs)
            }