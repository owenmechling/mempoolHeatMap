from collections import defaultdict

class OracleBuckets:
    """
    Simple rolling‑window bucket model.
    """
    def __init__(self, vsize_step=1000, feerate_step=1):
        self.vsize_step = vsize_step
        self.feerate_step = feerate_step
        self.buckets = defaultdict(int)   # (feerate_bucket) -> virtual bytes

    def ingest(self, tx):
        """
        `tx` is the *inner* dict from mempool.space containing vsize and fee.
        """
        vbytes  = tx["vsize"]
        feerate = tx["fee"] / vbytes
        fr_b = int(feerate // self.feerate_step)
        vs_b = int(vbytes  // self.vsize_step)
        self.buckets[(fr_b, vs_b)] += vbytes
        # optional: decay buckets here

    # backend/app/fee_oracle.py
    def ingest_block(self, block):
        fee_steps = block["feeRange"]            # e.g. len = 10
        block_vb  = int(block["blockVSize"])     # use vsize if present
        if not block_vb:                         # fallback
            block_vb = int(block["blocksize"] * 1000 / 4)

        chunk = block_vb // max(len(fee_steps), 1)

        for i, feerate in enumerate(fee_steps):
            fr_b = int(feerate // self.feerate_step)
            vs_b = i                             # ← row index!
            self.buckets[(fr_b, vs_b)] += chunk



    # backend/app/fee_oracle.py  (replace estimate)
    def estimate(self, max_blocks: int = 6, block_vbytes: int = 990_000):
        """
        Collapse (feerate,vsize) buckets down to feerate‑only bins and
        compute confirmation targets.
        """
        fee_totals = {}               # feerate_bin -> total vbytes across all vsize bins
        for (fr_b, _vs_b), vb in self.buckets.items():
            fee_totals[fr_b] = fee_totals.get(fr_b, 0) + vb

        totals, results = 0, {}
        # sort descending feerate so we simulate miner selection
        for fr_b in sorted(fee_totals, reverse=True):
            totals += fee_totals[fr_b]
            target = totals // block_vbytes + 1
            if target <= max_blocks and target not in results:
                results[target] = fr_b * self.feerate_step      # int, not tuple
        return results


    # --- new helpers --------------------------------------------------
    def snapshot(self):
        """
        Return three parallel arrays ready for Plotly:
        {
          "x": [feerate bins],   # e.g. [1,2,3,4,5 … 200]  (sat/vB)
          "y": [vsize bins],     # e.g. [1,2,3 … 100]      (k‑vbytes)
          "z": [[counts]]        # 2‑D list len(y) × len(x)
        }
        """
        # generate ordered sets so x/y stay stable frame‑to‑frame
        x_bins = sorted({k for k, _ in self.buckets})
        y_bins = sorted({v for _, v in self.buckets})
        z = [[self.buckets.get((x, y), 0) for x in x_bins] for y in y_bins]
        return {"x": x_bins, "y": y_bins, "z": z}

    def to_json(self):
        snap = self.snapshot()
        # log1p flattens huge numbers but keeps zero at 0
        import math
        snap["z"] = [[math.log1p(vb) for vb in row] for row in snap["z"]]
        import json, base64, zlib
        # compress a bit to keep Redis payload small
        return base64.b64encode(zlib.compress(
            json.dumps(self.snapshot()).encode()
        )).decode()