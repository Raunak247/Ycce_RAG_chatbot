#!/usr/bin/env python
"""
Manually ingest PDF/document files into FAISS index
Use this when you have specific documents to add to the database
"""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vectordb.vectordb_manager import VectorDBManager
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def ingest_file_to_faiss(file_path: str, branch: str = "", semester: str = ""):
    """
    Ingest a document file directly into FAISS

    Args:
        file_path: Path to the document (PDF, TXT, etc.)
        branch: Branch name (e.g., "AIML", "AIDS", "CSE")
        semester: Semester number (e.g., "4th", "IV")
    """

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False

    print("=" * 80)
    print(f"📄 Ingesting Document: {Path(file_path).name}")
    print("=" * 80)

    try:
        # =========================
        # Read file content
        # =========================

        if file_path.lower().endswith(".txt"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                print(f"❌ Failed to read TXT file: {e}")
                return False

        elif file_path.lower().endswith(".pdf"):
            content = ""

            # Try modern pypdf first (recommended)
            try:
                from pypdf import PdfReader
            except ImportError:
                try:
                    # Fallback to PyPDF2
                    from pypdf import PdfReader
                except ImportError:
                    print("❌ Please install one of these:")
                    print("   pip install pypdf")
                    print("   OR")
                    print("   pip install PyPDF2")
                    return False

            try:
                reader = PdfReader(file_path)

                for page in reader.pages:
                    try:
                        text = page.extract_text()
                        if text:
                            content += text + "\n"
                    except Exception:
                        continue

                if not content.strip():
                    print("❌ No extractable text found.")
                    print("   This PDF might be scanned (image-based).")
                    return False

            except Exception as e:
                print(f"❌ Failed to read PDF: {e}")
                return False

        else:
            print(f"❌ Unsupported format: {file_path}")
            return False

        # =========================
        # Validate content
        # =========================

        if not content or not content.strip():
            print("❌ File content is empty.")
            return False

        print(f"✅ File loaded ({len(content)} characters)")

        # =========================
        # Split content into chunks
        # =========================

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = splitter.split_text(content)

        if not chunks:
            print("❌ No chunks created from content.")
            return False

        print(f"✅ Split into {len(chunks)} chunks")

        # =========================
        # Create documents
        # =========================

        documents = []

        for i, chunk in enumerate(chunks):
            metadata = {
                "source": file_path,
                "chunk": i,
                "branch": branch,
                "semester": semester,
                "file_name": Path(file_path).name
            }

            doc = Document(page_content=chunk, metadata=metadata)
            documents.append(doc)

        # =========================
        # Add to FAISS
        # =========================

        vectordb = VectorDBManager()

        print(f"📊 Adding {len(documents)} documents to FAISS...")
        vectordb.add_documents(documents)

        print("\n✅ Document successfully ingested!")
        print(f"   - Branch: {branch}")
        print(f"   - Semester: {semester}")
        print(f"   - Chunks: {len(chunks)}")

        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("🔧 Manual Document Ingestion Tool")
    print("=" * 80)

    print("""
Usage:
  python manual_ingest.py <file_path> [branch] [semester]

Examples:
  python manual_ingest.py "AIDS_4th_sem_syllabus.txt" "AIDS" "4th"
  python manual_ingest.py "AIML_syllabus.pdf" "AIML" "3rd"
  python manual_ingest.py "admission_info.txt" "General" "All"

Supported formats:
  - .txt files (text)
  - .pdf files (requires pypdf or PyPDF2)
  - More formats can be added
    """)

    if len(sys.argv) < 2:
        print("\n📋 No arguments provided.")
        print("   Please provide file path as argument")
        return

    file_path = sys.argv[1]
    branch = sys.argv[2] if len(sys.argv) > 2 else ""
    semester = sys.argv[3] if len(sys.argv) > 3 else ""

    success = ingest_file_to_faiss(file_path, branch, semester)

    if success:
        print("\n" + "=" * 80)
        print("🎉 Ingestion complete! Chatbot will now have access to this content.")
        print("=" * 80)


if __name__ == "__main__":
    main()