"""Đối chiếu kết quả hai cách.

- Luôn so fingerprint trong results/etl_<tag>.json và results/elt_<tag>.json.
- Nếu hai file DB còn trong data/db/: so từng dòng của 15 bảng (EXCEPT hai chiều) và kiểm tra khóa ngoại.

Ví dụ: python src/verify.py small
"""
from __future__ import annotations

import json
import sqlite3
import sys

from common import DB_DIR, FINGERPRINTS, RESULT_DIR

# Bảng có id tra cứu thì đổi id thành tên, vì hai cách đánh số id khác nhau.
ROWS = {
    "titles": "SELECT t.title_id, y.name, primary_title, original_title, is_adult, start_year, end_year, "
              "runtime_minutes FROM {db}.titles t JOIN {db}.title_types y USING(type_id)",
    "title_genres": "SELECT title_id, name FROM {db}.title_genres JOIN {db}.genres USING(genre_id)",
    "name_professions": "SELECT name_id, name FROM {db}.name_professions JOIN {db}.professions USING(profession_id)",
    "title_principals": "SELECT title_id, ordering, name_id, name, job, characters "
                        "FROM {db}.title_principals JOIN {db}.categories USING(category_id)",
    **{t: f"SELECT name FROM {{db}}.{t}" for t in ("title_types", "genres", "professions", "categories")},
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    tag = sys.argv[1]
    etl, elt = (json.loads((RESULT_DIR / f"{m}_{tag}.json").read_text(encoding="utf-8")) for m in ("etl", "elt"))
    ok = True
    for t in FINGERPRINTS:
        same = etl["fingerprint"][t] == elt["fingerprint"][t]
        ok &= same
        print(f"{'KHỚP' if same else 'LỆCH'}  {t:<18} {etl['fingerprint'][t][0]:>13,} dòng")
        if not same:
            print("   etl", etl["fingerprint"][t], "\n   elt", elt["fingerprint"][t])

    paths = [DB_DIR / f"{m}_{tag}.db" for m in ("etl", "elt")]
    if all(p.exists() for p in paths):
        conn = sqlite3.connect(":memory:")
        for alias, p in zip(("a", "b"), paths):
            conn.execute(f"ATTACH ? AS {alias}", (str(p),))
        for t in FINGERPRINTS:
            q = ROWS.get(t, f"SELECT * FROM {{db}}.{t}")
            a, b = q.format(db="a"), q.format(db="b")
            diff = [conn.execute(f"SELECT COUNT(*) FROM ({x} EXCEPT {y})").fetchone()[0] for x, y in ((a, b), (b, a))]
            ok &= diff == [0, 0]
            print(f"EXCEPT {t:<18} etl-elt={diff[0]} elt-etl={diff[1]}")
        for alias in "ab":
            fk = conn.execute(f"PRAGMA {alias}.foreign_key_check").fetchall()
            ok &= not fk
            print(f"foreign_key_check {alias}: {len(fk)} lỗi")
    else:
        print("(Không còn file DB nên chỉ so fingerprint.)")
    print("KẾT LUẬN:", "hai cách cho dữ liệu giống nhau" if ok else "CÓ KHÁC BIỆT")
    sys.exit(not ok)


if __name__ == "__main__":
    main()
