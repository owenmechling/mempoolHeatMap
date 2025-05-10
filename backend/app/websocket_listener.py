"""
backend/app/websocket_listener.py
---------------------------------
Streams live mempool data from mempool.space, updates OracleBuckets,
and caches both heat‑map & fee estimates in Redis.

• Auto‑reconnect with exponential back‑off
• Debug prints every 5 s so 'docker logs listener' shows progress
"""

import asyncio, json, os, time
import aiohttp
import redis.asyncio as redis
from .fee_oracle import OracleBuckets

# ---------------------------------------------------------------------------#
WS_URL       = os.environ.get("WS_URL",
                              "wss://mempool.space/api/v1/ws")  # main‑net
REDIS_URL    = os.environ.get("REDIS_URL", "redis://redis:6379")
SUBSCRIPTION = {
    "action": "want",
    "data": ["mempool-blocks", "transactions"]  # ← plural!
}

HEATMAP_KEY  = "heatmap"
FEE_KEY_PREF = "fee-"            # fee-1, fee-2, ...

PUSH_INTERVAL = 1.5              # seconds between Redis writes
PRINT_EVERY   = 5.0              # seconds between console heartbeats
# ---------------------------------------------------------------------------#


async def run_listener():
    rdb     = redis.from_url(REDIS_URL, decode_responses=True)
    oracle  = OracleBuckets()
    backoff = 1

    while True:                       # reconnect loop
        try:
            async with aiohttp.ClientSession() as sess,\
                       sess.ws_connect(WS_URL) as ws:

                await ws.send_json(SUBSCRIPTION)
                print("[listener] ✅ connected + subscribed")
                tick, last_push, last_print = 0, time.time(), time.time()

                first10 = []      # TEMP: capture first ten event types for debugging

                async for msg in ws:
                    if msg.type is not aiohttp.WSMsgType.TEXT:
                        continue

                    # --- TEMP DEBUG: dump first 3 frames verbatim -------------------
                    if tick < 3:
                        print("RAW FRAME:", msg.data[:300], "…")  # truncate after 300 chars
                     # ----------------------------------------------------------------
                    obj = json.loads(msg.data)

                    ##--------------------------------------------------------------
                    # 1.  Batch of txs  (the typical 'transactions' channel)
                    if isinstance(obj, dict) and obj.get("mempool-blocks"):
                        # obj looks like {"mempool-blocks": [ {block1}, {block2}, … ]}
                        for blk in obj["mempool-blocks"]:
                            oracle.ingest_block(blk)
                            tick += 1

                    # 2.  Single tx  (some servers send 'transaction' not wrapped)
                    elif isinstance(obj, dict) and {"txid", "fee", "vsize"} <= obj.keys():
                        oracle.ingest(obj)
                        tick += 1

                    # 3.  Wrapped events we might care about later
                    elif isinstance(obj, dict) and obj.get("event") == "mempool-blocks":
                        pass   # ← ignoring for now
                    ##--------------------------------------------------------------

                    now = time.time()

                    if now - last_push >= PUSH_INTERVAL:
                        await rdb.set(HEATMAP_KEY, oracle.to_json(), ex=90)
                        for tgt, fee in oracle.estimate().items():
                            await rdb.set(f"{FEE_KEY_PREF}{tgt}", fee, ex=90)
                        last_push = now

                    if now - last_print >= PRINT_EVERY:
                        print(f"[listener] processed {tick} txs, "
                            f"{len(oracle.buckets)} buckets ({PRINT_EVERY}s)")
                        last_print = now


        except Exception as e:
            print(f"[listener] ⚠️  {type(e).__name__}: {e}  – reconnecting…")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)   # exponential back‑off (max 30 s)
        else:
            backoff = 1                      # reset on clean exit


if __name__ == "__main__":
    asyncio.run(run_listener())
