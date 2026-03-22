import json
import pathlib
import sys
from typing import Any
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WEBUI_ROOT = pathlib.Path(__file__).resolve().parent / "webui"
STATIC_ROOT = WEBUI_ROOT / "static"

_rag = None


def get_rag() -> Any:
    global _rag
    if _rag is None:
        from chatbot.rag_engine import SmartRAG
        _rag = SmartRAG()
    return _rag


class ChatHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: pathlib.Path, content_type: str) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send_file(WEBUI_ROOT / "index.html", "text/html; charset=utf-8")
            return

        if self.path == "/static/style.css":
            self._send_file(STATIC_ROOT / "style.css", "text/css; charset=utf-8")
            return

        if self.path == "/static/app.js":
            self._send_file(STATIC_ROOT / "app.js", "application/javascript; charset=utf-8")
            return

        if self.path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            content_len = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_len)
            payload = json.loads(raw.decode("utf-8") or "{}")
            message = (payload.get("message") or "").strip()

            if not message:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "message is required"})
                return

            rag = get_rag()
            result = rag.answer(message)
            answer = str(result.get("answer") or "").strip()
            raw_sources = result.get("sources") or []
            docs_count_raw = result.get("docs_count", 0)
            confidence_raw = result.get("confidence", 0.0)

            relevant_links = []
            evidence = []
            seen = set()
            for src in raw_sources[:8]:
                if not isinstance(src, dict):
                    continue
                metadata = src.get("metadata", {}) or {}
                link = (metadata.get("source_url") or metadata.get("source") or "").strip()
                if link and link not in seen:
                    seen.add(link)
                    relevant_links.append(link)

                snippet = str(src.get("content") or "").strip()
                if snippet:
                    snippet = " ".join(snippet.split())[:180]
                if link or snippet:
                    evidence.append(
                        {
                            "source": link,
                            "snippet": snippet,
                            "score": src.get("score"),
                        }
                    )

            try:
                docs_count = int(docs_count_raw)
            except (TypeError, ValueError):
                docs_count = 0

            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError):
                confidence = 0.0

            self._send_json(
                HTTPStatus.OK,
                {
                    "answer": answer,
                    "docs_count": docs_count,
                    "confidence": confidence,
                    "relevant_links": relevant_links,
                    "evidence": evidence[:5],
                },
            )
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"chat processing failed: {exc}"},
            )

    def log_message(self, format: str, *args) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8502) -> None:
    server = ThreadingHTTPServer((host, port), ChatHandler)
    print(f"[WEB] YCCE Chat UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
