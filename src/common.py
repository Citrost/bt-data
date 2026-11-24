"""Phần dùng chung cho cả hai cách: schema, PRAGMA, đọc file, đo thời gian, đối chiếu."""
from __future__ import annotations

import argparse
import ctypes
import gzip
import itertools
import json
import platform
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_DIR = ROOT / "data" / "db"
RESULT_DIR = ROOT / "results"
SCHEMA = ROOT / "sql" / "schema.sql"

# Thứ tự nạp: bảng cha trước, bảng con sau (vì có khóa ngoại).
FILES = ["title.basics", "name.basics", "title.ratings", "title.episode",
         "title.crew", "title.akas", "title.principals"]

COMMIT_ROWS = 500_000  # cả hai cách đều commit sau mỗi 500k dòng nguồn


def connect(db: Path) -> sqlite3.Connection:
    """PRAGMA giống hệt nhau cho hai cách để chỉ còn khác cơ chế insert."""
    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -262144")  # 256 MB
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def new_database(db: Path) -> sqlite3.Connection:
    """Tạo DB trống. Từ chối ghi đè DB cũ để không xóa nhầm."""
    if db.exists():
        sys.exit(f"{db} đã tồn tại. Hãy xóa file này hoặc đổi --tag.")
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def read_rows(name: str, limit: int | None) -> Iterator[list[str]]:
    """Đọc TSV nén theo dòng. IMDb không dùng dấu nháy kiểu CSV nên chỉ cần split tab."""
    with gzip.open(RAW_DIR / f"{name}.tsv.gz", "rt", encoding="utf-8", newline="\n") as f:
        next(f)
        for line in itertools.islice(f, limit):
            yield line.rstrip("\n").split("\t")


def chunks(it: Iterator, size: int) -> Iterator[list]:
    while block := list(itertools.islice(it, size)):
        yield block


def peak_ram_mb() -> float:
    if platform.system() != "Windows":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in ("peak_ws", "ws", "a", "b", "c", "d", "pf", "peak_pf")]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.peak_ws / 1024 / 1024


# Mỗi câu trả về số dòng và tổng kiểm tra không phụ thuộc id của bảng tra cứu.
FINGERPRINTS = {
    "titles": "SELECT COUNT(*), SUM(title_id), SUM(is_adult), SUM(start_year), SUM(end_year), "
              "SUM(runtime_minutes), SUM(length(primary_title)), SUM(length(original_title)) FROM titles",
    "names": "SELECT COUNT(*), SUM(name_id), SUM(birth_year), SUM(death_year), SUM(length(primary_name)) FROM names",
    "title_genres": "SELECT COUNT(*), SUM(title_id), SUM(length(name)) FROM title_genres JOIN genres USING(genre_id)",
    "name_professions": "SELECT COUNT(*), SUM(name_id), SUM(length(name)) FROM name_professions "
                        "JOIN professions USING(profession_id)",
    "name_known_titles": "SELECT COUNT(*), SUM(name_id), SUM(title_id) FROM name_known_titles",
    "title_ratings": "SELECT COUNT(*), SUM(title_id), SUM(CAST(round(average_rating*10) AS INT)), SUM(num_votes) "
                     "FROM title_ratings",
    "episodes": "SELECT COUNT(*), SUM(title_id), SUM(parent_id), SUM(season), SUM(episode) FROM episodes",
    "title_directors": "SELECT COUNT(*), SUM(title_id), SUM(name_id) FROM title_directors",
    "title_writers": "SELECT COUNT(*), SUM(title_id), SUM(name_id) FROM title_writers",
    "title_akas": "SELECT COUNT(*), SUM(title_id), SUM(ordering), SUM(length(title)), COUNT(region), COUNT(language), "
                  "COUNT(types), COUNT(attributes), SUM(is_original) FROM title_akas",
    "title_principals": "SELECT COUNT(*), SUM(title_id), SUM(ordering), SUM(name_id), SUM(length(name)), "
                        "SUM(length(job)), SUM(length(characters)) FROM title_principals "
                        "JOIN categories USING(category_id)",
    "title_types": "SELECT COUNT(*), SUM(length(name)) FROM title_types",
    "genres": "SELECT COUNT(*), SUM(length(name)) FROM genres",
    "professions": "SELECT COUNT(*), SUM(length(name)) FROM professions",
    "categories": "SELECT COUNT(*), SUM(length(name)) FROM categories",
}


def fingerprint(conn: sqlite3.Connection) -> dict[str, list]:
    return {t: list(conn.execute(q).fetchone()) for t, q in FINGERPRINTS.items()}


def parse_args(doc: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, help="số dòng tối đa đọc từ MỌI file")
    p.add_argument("--limit-akas", type=int, help="số dòng tối đa của title.akas")
    p.add_argument("--limit-principals", type=int, help="số dòng tối đa của title.principals")
    p.add_argument("--tag", default="run", help="tên lần chạy, dùng đặt tên file DB và kết quả")
    p.add_argument("--drop-db", action="store_true", help="xóa file DB vừa tạo sau khi đo xong")
    return p.parse_args()


def run(method: str, load_file, args: argparse.Namespace) -> None:
    """Vòng lặp chung: nạp từng file, đo thời gian, ghi kết quả JSON."""
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    missing = [f for f in FILES if not (RAW_DIR / f"{f}.tsv.gz").exists()]
    if missing:
        sys.exit(f"Thiếu file {missing}. Hãy chạy: python src/download_data.py")
    db = DB_DIR / f"{method}_{args.tag}.db"
    conn = new_database(db)
    state: dict = {}
    per_file = {}
    t_all = time.perf_counter()
    for name in FILES:
        limit = {"title.akas": args.limit_akas,
                 "title.principals": args.limit_principals}.get(name) or args.limit
        t0 = time.perf_counter()
        n = load_file(conn, name, limit, state)
        dt = time.perf_counter() - t0
        per_file[name] = {"rows": n, "seconds": round(dt, 2)}
        print(f"[{method}] {name:<17} {n:>12,} dòng | {dt:8.1f}s | {n / dt:>9,.0f} dòng/s", flush=True)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    total_seconds = time.perf_counter() - t_all  # tính cả checkpoint cuối
    ram = peak_ram_mb()
    rows = sum(v["rows"] for v in per_file.values())
    size = db.stat().st_size / 1e6
    print(f"[{method}] TỔNG {rows:,} dòng nguồn | {total_seconds:.1f}s | "
          f"{rows / total_seconds:,.0f} dòng/s | DB {size:,.0f} MB | RAM đỉnh {ram:,.0f} MB", flush=True)
    fp = fingerprint(conn)
    conn.close()
    result = {"method": method, "tag": args.tag, "source_rows": rows,
              "inserted_rows": sum(v[0] for v in fp.values()),
              "total_seconds": round(total_seconds, 2), "db_mb": round(size, 1),
              "peak_ram_mb": round(ram, 1), "per_file": per_file,
              "python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "fingerprint": fp}
    RESULT_DIR.mkdir(exist_ok=True)
    (RESULT_DIR / f"{method}_{args.tag}.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.drop_db:
        db.unlink()
