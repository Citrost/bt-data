"""Đổi TỪNG yếu tố một trên cùng dữ liệu (title.basics, 1 triệu dòng) để biết yếu tố nào ảnh hưởng.

Dữ liệu được đọc sẵn vào RAM nên thời gian đo chỉ là insert + commit + checkpoint.
Mỗi cấu hình chạy 3 lần trên DB mới, lấy trung vị. Kết quả: results/ablation.md
"""
from __future__ import annotations

import statistics
import sys
import tempfile
import time
import sqlite3
from pathlib import Path

from common import DB_DIR, RESULT_DIR, read_rows

N = 1_000_000
REPEATS = 3
DDL = ("CREATE TABLE t (title_id INTEGER PRIMARY KEY, type TEXT, primary_title TEXT, original_title TEXT, "
       "start_year TEXT)")
INDEX = "CREATE INDEX ix_t ON t(primary_title)"
SQL = "INSERT INTO t VALUES (?,?,?,?,?)"
BASE = {"rows": N, "batch": 10_000, "commit": None, "journal": "WAL", "sync": "NORMAL", "index": "none"}

CASES = [
    ("Mốc so sánh: batch 10k, commit 1 lần, WAL + NORMAL", {}),
    ("Lô executemany: 100 dòng", {"batch": 100}),
    ("Lô executemany: 1.000 dòng", {"batch": 1_000}),
    ("Lô executemany: 100.000 dòng", {"batch": 100_000}),
    ("Lô executemany: 1 dòng (execute từng dòng, vẫn 1 transaction)", {"batch": 1}),
    ("Commit mỗi 100 dòng", {"batch": 100, "commit": 100}),
    ("Commit mỗi 1.000 dòng", {"batch": 1_000, "commit": 1_000}),
    ("Commit mỗi 10.000 dòng", {"commit": 10_000}),
    ("Commit mỗi 1.000 dòng, journal DELETE + FULL (mặc định của SQLite)",
     {"batch": 1_000, "commit": 1_000, "journal": "DELETE", "sync": "FULL"}),
    ("Journal DELETE + FULL, commit 1 lần", {"journal": "DELETE", "sync": "FULL"}),
    ("Journal OFF + sync OFF, commit 1 lần (không an toàn)", {"journal": "OFF", "sync": "OFF"}),
    ("Có index phụ, tạo TRƯỚC khi nạp", {"index": "before"}),
    ("Có index phụ, tạo SAU khi nạp", {"index": "after"}),
    ("Commit từng dòng, DELETE + FULL (chỉ 5.000 dòng)",
     {"rows": 5_000, "batch": 1, "commit": 1, "journal": "DELETE", "sync": "FULL"}),
]


def measure(data: list[tuple], cfg: dict, folder: Path) -> float:
    db = folder / "ablation.db"
    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute(f"PRAGMA journal_mode = {cfg['journal']}")
    conn.execute(f"PRAGMA synchronous = {cfg['sync']}")
    conn.execute("PRAGMA cache_size = -262144")
    conn.execute(DDL)
    if cfg["index"] == "before":
        conn.execute(INDEX)
    rows, batch, commit = cfg["rows"], cfg["batch"], cfg["commit"]
    t0 = time.perf_counter()
    conn.execute("BEGIN")
    since = 0
    for i in range(0, rows, batch):
        if batch == 1:
            conn.execute(SQL, data[i])
        else:
            conn.executemany(SQL, data[i:i + batch])
        since += batch
        if commit and since >= commit:
            conn.execute("COMMIT")
            conn.execute("BEGIN")
            since = 0
    if cfg["index"] == "after":
        conn.execute(INDEX)
    conn.execute("COMMIT")
    if cfg["journal"] == "WAL":
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dt = time.perf_counter() - t0
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == rows
    conn.close()
    return dt


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    data = [(int(r[0][2:]), r[1], r[2], r[3], r[5]) for r in read_rows("title.basics", N)]
    DB_DIR.mkdir(parents=True, exist_ok=True)
    times: dict[str, list[float]] = {name: [] for name, _ in CASES}
    for _ in range(REPEATS):  # chạy xen kẽ để nhiễu của máy chia đều cho các cấu hình
        for name, change in CASES:
            with tempfile.TemporaryDirectory(dir=DB_DIR) as tmp:  # thư mục tạm do chính script tạo
                times[name].append(measure(data, {**BASE, **change}, Path(tmp)))
    base = N / statistics.median(times[CASES[0][0]])
    lines = [f"`title.basics`, {N:,} dòng, trung vị {REPEATS} lần chạy (nhỏ nhất – lớn nhất).", "",
             "| Cấu hình | Giây | Dòng/giây | So với mốc |", "|---|---:|---:|---:|"]
    for name, change in CASES:
        ts = times[name]
        med = statistics.median(ts)
        speed = change.get("rows", N) / med
        lines.append(f"| {name} | {med:.2f} ({min(ts):.2f} – {max(ts):.2f}) | {speed:,.0f} | {speed / base:.2f}x |")
    (RESULT_DIR / "ablation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
