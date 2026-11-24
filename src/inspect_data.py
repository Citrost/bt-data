"""Đếm số dòng thật, kiểm tra số cột và độ dài lớn nhất của từng cột trong data/raw/.

Đọc hết file gzip nên cũng xác nhận luôn file không bị hỏng (CRC).
"""
from __future__ import annotations

import gzip
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "results" / "row_counts.md"


def inspect(path: Path) -> dict:
    rows = bad = quotes = raw_bytes = 0
    with gzip.open(path, "rb") as f:
        header = f.readline().rstrip(b"\r\n").split(b"\t")
        n = len(header)
        max_len = [0] * n
        nulls = [0] * n
        sample = None
        for line in f:
            raw_bytes += len(line)
            rows += 1
            cols = line.rstrip(b"\r\n").split(b"\t")
            if len(cols) != n:
                bad += 1
                continue
            if sample is None:
                sample = line.decode("utf-8").strip()
            if b'"' in line or line.count(b"\\") != cols.count(b"\\N"):
                quotes += 1
            for i, c in enumerate(cols):
                if c == b"\\N":
                    nulls[i] += 1
                elif len(c) > max_len[i]:
                    max_len[i] = len(c)
    return {
        "name": path.name, "rows": rows, "bad": bad, "quotes": quotes,
        "gz": path.stat().st_size, "raw": raw_bytes, "sample": sample,
        "cols": [(h.decode(), m, z) for h, m, z in zip(header, max_len, nulls)],
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    paths = sorted(RAW_DIR.glob("*.tsv.gz"))
    with ProcessPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(inspect, paths))
    lines = ["| File | Số dòng | Dung lượng nén | Dung lượng TSV | Dòng sai số cột |",
             "|---|---:|---:|---:|---:|"]
    for r in results:
        lines.append(f"| {r['name']} | {r['rows']:,} | {r['gz'] / 1e6:,.0f} MB | "
                     f"{r['raw'] / 1e6:,.0f} MB | {r['bad']:,} |")
        print(f"\n{r['name']} rows={r['rows']:,} bad={r['bad']} quote_or_backslash={r['quotes']:,}")
        print("  mẫu:", r["sample"])
        for h, m, z in r["cols"]:
            print(f"  {h:<20} max_bytes={m:<6} null={z:,}")
    total = sum(r["rows"] for r in results)
    lines.append(f"| **Tổng** | **{total:,}** | | | |")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
