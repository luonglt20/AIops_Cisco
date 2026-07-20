"""
MerakiMind — Semantic Memory Engine (ChromaDB + Sentence-Transformers)
Lưu trữ và retrieve các sự cố mạng tương tự bằng vector similarity.
100% local — không cần API key hay internet sau khi download model lần đầu.
"""
import os
import json
import hashlib
import threading
from datetime import datetime, timezone

# ── ChromaDB + Sentence-Transformers ──────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    _MEMORY_AVAILABLE = True
except ImportError:
    _MEMORY_AVAILABLE = False

# ── Constants ──────────────────────────────────────────────────────────────────
DATA_DIR        = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME = "meraki_incidents"
EMBED_MODEL     = "all-MiniLM-L6-v2"   # 80MB, fast, 384-dim
TOP_K           = 3                      # số sự cố tương tự cần retrieve

_client     = None
_collection = None
_embedder   = None
_init_lock  = threading.Lock()


def _init():
    """Lazy init — chỉ load model 1 lần."""
    global _client, _collection, _embedder
    if _collection is not None:
        return True
    if not _MEMORY_AVAILABLE or os.environ.get("DISABLE_CHROMA") == "1":
        print("[Memory] chromadb / sentence-transformers chưa cài hoặc bị disable. Bỏ qua semantic memory.")
        return False
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=DATA_DIR)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        _embedder = SentenceTransformer(EMBED_MODEL)
        print(f"[Memory] Initialized. Collection has {_collection.count()} incidents.")
        return True
    except Exception as e:
        print(f"[Memory] Init failed: {e}")
        return False


def _build_text(
    alert_type: str,
    device_model: str,
    firmware: str,
    diagnosis: str,
) -> str:
    """Build a single text string for embedding."""
    return (
        f"Alert: {alert_type}. "
        f"Device Model: {device_model}. "
        f"Firmware: {firmware}. "
        f"Diagnosis: {diagnosis}."
    )


def save_incident(
    alert_type: str,
    device_model: str,
    firmware: str,
    diagnosis: str,
    resolution: str = "",
    serial: str = "",
    org_id: str = "",
) -> str | None:
    """
    Save an incident to the vector store.
    Returns the incident_id if successful, None otherwise.
    """
    with _init_lock:
        if not _init():
            return None

    text = _build_text(alert_type, device_model, firmware, diagnosis)
    
    # Deterministic ID: same device+type+firmware+day won't duplicate
    raw_id = f"{serial}:{alert_type}:{firmware}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    incident_id = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

    metadata = {
        "alert_type":    alert_type,
        "device_model":  device_model,
        "firmware":      firmware,
        "serial":        serial,
        "org_id":        org_id,
        "resolution":    resolution[:500] if resolution else "",
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }

    try:
        embedding = _embedder.encode(text).tolist()
        _collection.upsert(
            ids=[incident_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata],
        )
        print(f"[Memory] Saved incident id={incident_id} ({alert_type} / {device_model})")
        return incident_id
    except Exception as e:
        print(f"[Memory] Save failed: {e}")
        return None


def retrieve_similar(
    alert_type: str,
    device_model: str,
    firmware: str,
    diagnosis_hint: str = "",
    org_id: str = "",
    top_k: int = TOP_K,
) -> list[dict]:
    """
    Retrieve the top-k most similar past incidents using cosine similarity.
    Returns list of dicts with fields: id, document, metadata, distance.
    """
    with _init_lock:
        if not _init():
            return []

    if _collection.count() == 0:
        return []

    query_text = _build_text(alert_type, device_model, firmware, diagnosis_hint)
    try:
        query_embedding = _embedder.encode(query_text).tolist()
        query_args = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, _collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if org_id:
            query_args["where"] = {"org_id": org_id}
            
        results = _collection.query(**query_args)
        
        similar = []
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            # Only include highly similar cases (cosine distance < 0.25, i.e., > 75% similarity)
            if distance < 0.25:
                similar.append({
                    "id":       doc_id,
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "similarity": round(1 - distance, 3),
                })
        print(f"[Memory] Retrieved {len(similar)} similar incidents for {alert_type}/{device_model}")
        return similar
    except Exception as e:
        print(f"[Memory] Retrieve failed: {e}")
        return []


def build_memory_context(similar_cases: list[dict]) -> str:
    """
    Build a short Vietnamese text context from similar cases.
    Injected into agent blackboard for richer diagnosis.
    """
    if not similar_cases:
        return ""
    
    lines = [f"📚 KÝ ỨC HỆ THỐNG — {len(similar_cases)} sự cố tương tự đã được ghi nhận trước đó:"]
    for i, case in enumerate(similar_cases, 1):
        meta = case.get("metadata", {})
        sim  = case.get("similarity", 0)
        res_text = meta.get('resolution', 'Không rõ')
        if len(res_text) > 250:
            res_text = res_text[:250].rsplit(' ', 1)[0] + "..."
        lines.append(
            f"  [{i}] (tương đồng {sim:.0%}) "
            f"Model={meta.get('device_model','?')}, "
            f"Firmware={meta.get('firmware','?')}, "
            f"AlertType={meta.get('alert_type','?')}, "
            f"Kết quả: {res_text}"
        )
    return "\n".join(lines)
