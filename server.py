"""
MerakiMind — HTTP Server (entry point)
Thin REST bridge — all business logic lives in pipeline.py and agents/.
"""
import json
import sys
import functools
print = functools.partial(print, flush=True)
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from config import SERVER_PORT
from pipeline import fetch_all_orgs, run_analyze_pipeline, build_response
from api import pdf_export, trend_db


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    # ── CORS helpers ──────────────────────────────
    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self._send_cors()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            print("[Server] Client disconnected before response was fully sent (BrokenPipe). Ignoring.")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw)
        except Exception:
            return {}

    # ── GET ───────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/health":
            self._json({
                "status": "ok",
                "server": "MerakiMind v3.0 — AIOps Platform",
                "time":   datetime.now().isoformat(),
                "features": ["telemetry", "semantic_memory", "trend_db", "pdf_export"],
            })

        elif path == "/api/data":
            query = urlparse(self.path).query
            force = "refresh=true" in query or "force=true" in query
            timespan = 604800  # Default 7 days
            for part in query.split("&"):
                if part.startswith("timespan="):
                    try:
                        timespan = int(part.split("=", 1)[1])
                    except Exception:
                        pass
            print(f"[Server] Fetching all org data (force_refresh={force}, timespan={timespan}s)...")
            self._json({
                "status":    "ok",
                "data":      fetch_all_orgs(force_refresh=force, timespan=timespan),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        elif path == "/api/trend-stats":
            query   = urlparse(self.path).query
            org_id  = ""
            for part in query.split("&"):
                if part.startswith("orgId="):
                    org_id = part.split("=", 1)[1]
            stats = trend_db.get_org_stats(org_id) if org_id else {"total_incidents_24h": 0, "most_troubled_devices": []}
            persistent = trend_db.get_persistent_devices(threshold=3)
            self._json({
                "status": "ok",
                "stats": stats,
                "persistent_devices": persistent,
            })

        else:
            self.send_response(404)
            self.end_headers()


    # ── POST ──────────────────────────────────────
    def do_POST(self):
        path    = urlparse(self.path).path
        payload = self._read_body()

        if path == "/api/analyze-alert":
            print("[Server] 🤖 Multi-Agent pipeline v3 starting...")
            alert_data = payload.get("alert", {})
            org_id     = payload.get("orgId", "")
            model_mode = payload.get("modelMode", "groq")

            # Resolve org context
            all_orgs  = fetch_all_orgs()
            org_data  = next(
                (o for o in all_orgs if o["id"] == org_id),
                all_orgs[0] if all_orgs else {}
            )

            state     = run_analyze_pipeline(alert_data, org_data, model_mode=model_mode)
            generated = datetime.now(timezone.utc).isoformat()
            response  = build_response(state, generated)
            self._json(response)

        elif path == "/api/export-pdf":
            # Build a minimal pipeline_result dict from POST body
            print("[Server] 📄 Generating PDF report...")
            pdf_bytes = pdf_export.generate_pdf(payload)
            if pdf_bytes:
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", 'attachment; filename="MerakiMind_Report.pdf"')
                self.send_header("Content-Length", len(pdf_bytes))
                self._send_cors()
                self.end_headers()
                self.wfile.write(pdf_bytes)
            else:
                self._json({"status": "error", "message": "PDF generation failed."}, 500)

        else:
            self.send_response(404)
            self.end_headers()



if __name__ == "__main__":
    print("""
╬══════════════════════════════════════════════════╬
║    MerakiMind v3.0 — AIOps Platform              ║
║                                                  ║
║  • Real Telemetry Enrichment (WAN/RF/Events)   ║
║  • Full Multi-Tool ReAct Agent Loops           ║
║  • ChromaDB Semantic Memory (local)            ║
║  • Pydantic Structured Output                  ║
║  • SQLite Trend & Anomaly Detection            ║
║  • PDF Report Export                          ║
╞══════════════════════════════════════════════════╡
║  http://localhost:8765/api/health               ║
╚══════════════════════════════════════════════════╝
""")
    server = ThreadingHTTPServer(("0.0.0.0", SERVER_PORT), Handler)
    print(f"[Server] Listening on :{SERVER_PORT} ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Stopped.")
