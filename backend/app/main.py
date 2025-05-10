import json, base64, zlib
from fastapi import FastAPI, HTTPException
import redis.asyncio as redis
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

app = FastAPI(title="Mempool Fee Oracle")
r = redis.from_url("redis://redis:6379", decode_responses=True)

@app.get("/api/fee")
async def fee(target_blocks: int = 1):
    """
    Return sat/vB estimate to confirm within `target_blocks`.
    """
    key = f"fee-{target_blocks}"
    value = await r.get(key)
    if value is None:
        raise HTTPException(404, f"No estimate yet for {target_blocks} blocks")
    return {"feerate": float(value)}

@app.get("/api/heatmap")
async def heatmap():
    blob = await r.get("heatmap")
    if blob is None:
        raise HTTPException(404, "Heat‑map not ready")
    raw = zlib.decompress(base64.b64decode(blob))
    return json.loads(raw)
