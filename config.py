import os
from pathlib import Path

# Load .env file if available locally
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# ─────────────────────────────────────────────────
# MerakiMind — Environment Configuration
# ─────────────────────────────────────────────────

MERAKI_API_KEY = os.getenv("MERAKI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_raw_groq_keys = os.getenv("GROQ_API_KEYS", "").split(",")
GROQ_API_KEYS = [k.strip() for k in _raw_groq_keys if k.strip()]
if not GROQ_API_KEYS:
    single_key = os.getenv("GROQ_API_KEY", "")
    if single_key:
        GROQ_API_KEYS = [single_key]

GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""

MERAKI_BASE = "https://api.meraki.com/api/v1"
GEMINI_URL  = (
    "https://generativelanguage.googleapis.com/v1beta"
    f"/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
)
GROQ_URL         = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL_FAST  = "llama-3.1-8b-instant"     # Super-fast & ultra-low token usage for sub-agent data collectors
GROQ_MODEL_SMART = "llama-3.3-70b-versatile"  # High reasoning capability for orchestrators & final synthesis
GROQ_MODEL        = GROQ_MODEL_SMART

SERVER_PORT = int(os.getenv("PORT", os.getenv("SERVER_PORT", 8765)))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")


