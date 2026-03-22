from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from vectordb.vectordb_manager import VectorDBManager
from crawler.bfs_crawler import bfs_crawl
from detector.change_detector import detect_changes
from ingestion.ingest_pipeline import ingest_items
from config import SIMILARITY_THRESHOLD, BASE_URL


class SmartRAG:

    def __init__(self):
        print("🧠 SmartRAG initializing...")
        self.vectordb = VectorDBManager()

        self.llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0.3
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

Context from YCCE Database:
{context}

Question/Query: {question}

Answer:"""
        )

    def _preprocess_query(self, query: str) -> str:
        """Clean and normalize query"""
        return query.strip().lower() if query else ""

    def _generate_query_variants(self, query: str) -> list:
        """Generate query variants for better retrieval (SINGLE ANSWER MODE)"""
        # FIXED: Return only the original query to prevent multiple different answers
        # Variants were causing 6 different answers - now we use single query for consistency
        return [query]

    def _retrieve_context(self, query: str, k: int = 7) -> tuple[str, list]:
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
            sorted_docs = sorted(all_docs.values(), key=lambda x: x["score"])[:k]
            
            # Build context with better formatting
            context_parts = []
            for i, doc in enumerate(sorted_docs, 1):
                context_parts.append(f"[Document {i}]\n{doc['content']}")
            
            context = "\n\n---\n\n".join(context_parts)
            return context, sorted_docs
            
        except Exception as e:
            print(f"[ERROR] Retrieval failed: {e}")
            return "", []

    def answer(self, query: str) -> dict:
        """Generate answer using enhanced RAG pipeline"""
        print(f"🔍 Processing query: {query}")
        
        # Retrieve relevant documents with higher k value
        context, retrieved_docs = self._retrieve_context(query, k=7)
        
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
        print(f"✅ Retrieved {len(retrieved_docs)} documents (avg relevance score: {avg_score:.4f})")
        
        try:
            # Check retrieval quality - lower score = better match (cosine similarity)
            # If score is high (poor match), inform user
            if avg_score > 0.7:  # Very poor match
                print(f"⚠️ Low relevance match (score: {avg_score:.4f}) - returning best available docs")
                # log the contents and scores for debugging
                for idx, d in enumerate(retrieved_docs[:5], start=1):
                    print(f"   doc {idx} score={d.get('original_score', d['score']):.4f} preview={d['content'][:100]!r}")
                return {
                    "answer": "The information I found has low relevance to your query. Here are the closest matches:\n\n" + 
                             "\n\n".join([d["content"][:300] + "..." for d in retrieved_docs[:2]]),
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