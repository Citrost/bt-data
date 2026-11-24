"""Tải 7 file IMDb Non-Commercial Datasets vào data/raw/.

Nguồn: https://datasets.imdbws.com/ (chỉ dùng cho mục đích cá nhân, phi thương mại).
File đã tải đủ dung lượng sẽ được bỏ qua, nên có thể chạy lại khi mạng bị ngắt.
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

BASE_URL = "https://datasets.imdbws.com/"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
FILES = [
    "title.ratings.tsv.gz",
    "title.episode.tsv.gz",
    "title.crew.tsv.gz",
    "title.basics.tsv.gz",
    "name.basics.tsv.gz",
    "title.akas.tsv.gz",
    "title.principals.tsv.gz",
]
CHUNK = 1024 * 1024
RETRIES = 3


def download(name: str) -> None:
    dest = RAW_DIR / name
    with urllib.request.urlopen(BASE_URL + name, timeout=60) as resp:
        expected = int(resp.headers["Content-Length"])
        if dest.exists() and dest.stat().st_size == expected:
            print(f"[SKIP] {name} ({expected:,} bytes)", flush=True)
            return
        tmp = dest.with_name(dest.name + ".part")
        t0 = time.perf_counter()
        with tmp.open("wb") as out:
            while block := resp.read(CHUNK):
                out.write(block)
    size = tmp.stat().st_size
    if size != expected:
        raise OSError(f"{name}: nhận {size:,} bytes, cần {expected:,}")
    tmp.replace(dest)
    print(f"[OK]   {name} {size:,} bytes | {time.perf_counter() - t0:.0f}s", flush=True)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        for attempt in range(1, RETRIES + 1):
            try:
                download(name)
                break
            except OSError as exc:
                print(f"[LỖI]  {name} lần {attempt}/{RETRIES}: {exc}", flush=True)
                if attempt == RETRIES:
                    raise
                time.sleep(5)


if __name__ == "__main__":
    main()
