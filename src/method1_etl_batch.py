"""Cách 1 - ETL: Python tách/ép kiểu/lọc từng dòng rồi executemany thẳng vào bảng đích.

Ví dụ: python src/method1_etl_batch.py --limit 1000000 --tag small
"""
from __future__ import annotations

import sqlite3

from common import COMMIT_ROWS, chunks, parse_args, read_rows, run

BATCH = 10_000
NULL = "\\N"
MAX_ID = 100_000_000  # id IMDb có tối đa 8 chữ số


def num(s: str) -> int | None:
    return int(s) if s.isdecimal() else None


def text(s: str) -> str | None:
    return None if s == NULL else s


def items(s: str) -> list[str]:
    return [] if s == NULL else s.split(",")


class Lookup:
    """Bảng tra cứu: giữ dict trong RAM, gặp giá trị mới thì insert ngay."""

    def __init__(self, conn: sqlite3.Connection, table: str, key: str):
        self.conn, self.ids = conn, {}
        self.sql = f"INSERT INTO {table} ({key}, name) VALUES (?, ?)"

    def get(self, name: str) -> int:
        i = self.ids.get(name)
        if i is None:
            i = self.ids[name] = len(self.ids) + 1
            self.conn.execute(self.sql, (i, name))
        return i


INSERTS = {
    "title.basics": {
        "titles": "INSERT INTO titles VALUES (?,?,?,?,?,?,?,?)",
        "title_genres": "INSERT OR IGNORE INTO title_genres VALUES (?,?)"},
    "name.basics": {
        "names": "INSERT INTO names VALUES (?,?,?,?)",
        "name_professions": "INSERT OR IGNORE INTO name_professions VALUES (?,?)",
        "name_known_titles": "INSERT OR IGNORE INTO name_known_titles VALUES (?,?)"},
    "title.ratings": {"title_ratings": "INSERT INTO title_ratings VALUES (?,?,?)"},
    "title.episode": {"episodes": "INSERT INTO episodes VALUES (?,?,?,?)"},
    "title.crew": {
        "title_directors": "INSERT OR IGNORE INTO title_directors VALUES (?,?)",
        "title_writers": "INSERT OR IGNORE INTO title_writers VALUES (?,?)"},
    "title.akas": {"title_akas": "INSERT INTO title_akas VALUES (?,?,?,?,?,?,?,?)"},
    "title.principals": {"title_principals": "INSERT INTO title_principals VALUES (?,?,?,?,?,?)"},
}


def transform(name: str, rows: list[list[str]], out: dict[str, list], st: dict) -> None:
    has_title, has_name = st["titles"], st["names"]  # bitmap id đã nạp, để lọc dòng mồ côi
    if name == "title.basics":
        titles, tg = out["titles"], out["title_genres"]
        types, genres = st["types"], st["genres"]
        for t, typ, pt, ot, adult, sy, ey, rt, gs in rows:
            i = int(t[2:])
            has_title[i] = 1
            titles.append((i, types.get(typ), pt, ot, int(adult), num(sy), num(ey), num(rt)))
            for g in items(gs):
                tg.append((i, genres.get(g)))
    elif name == "name.basics":
        names, np, nk = out["names"], out["name_professions"], out["name_known_titles"]
        profs = st["professions"]
        for n, pn, by, dy, ps, ks in rows:
            i = int(n[2:])
            has_name[i] = 1
            names.append((i, text(pn), num(by), num(dy)))
            for p in items(ps):
                np.append((i, profs.get(p)))
            for k in items(ks):
                t = int(k[2:])
                if has_title[t]:
                    nk.append((i, t))
    elif name == "title.ratings":
        buf = out["title_ratings"]
        for t, r, v in rows:
            i = int(t[2:])
            if has_title[i]:
                buf.append((i, float(r), int(v)))
    elif name == "title.episode":
        buf = out["episodes"]
        for t, p, s, e in rows:
            i, j = int(t[2:]), int(p[2:])
            if has_title[i] and has_title[j]:
                buf.append((i, j, num(s), num(e)))
    elif name == "title.crew":
        ds_out, ws_out = out["title_directors"], out["title_writers"]
        for t, ds, ws in rows:
            i = int(t[2:])
            if not has_title[i]:
                continue
            for src, dst in ((ds, ds_out), (ws, ws_out)):
                for n in items(src):
                    j = int(n[2:])
                    if has_name[j]:
                        dst.append((i, j))
    elif name == "title.akas":
        buf = out["title_akas"]
        for t, o, title, reg, lang, ty, at, orig in rows:
            i = int(t[2:])
            if has_title[i]:
                buf.append((i, int(o), title, text(reg), text(lang), text(ty), text(at), num(orig)))
    elif name == "title.principals":
        buf, cats = out["title_principals"], st["categories"]
        for t, o, n, c, job, chars in rows:
            i, j = int(t[2:]), int(n[2:])
            cat = cats.get(c)
            if has_title[i] and has_name[j]:
                buf.append((i, int(o), j, cat, text(job), text(chars)))


def load_file(conn: sqlite3.Connection, name: str, limit: int | None, st: dict) -> int:
    if not st:
        st.update(titles=bytearray(MAX_ID), names=bytearray(MAX_ID),
                  types=Lookup(conn, "title_types", "type_id"),
                  genres=Lookup(conn, "genres", "genre_id"),
                  professions=Lookup(conn, "professions", "profession_id"),
                  categories=Lookup(conn, "categories", "category_id"))
    inserts = INSERTS[name]
    total = since_commit = 0
    conn.execute("BEGIN")
    try:
        for rows in chunks(read_rows(name, limit), BATCH):
            out: dict[str, list] = {t: [] for t in inserts}
            transform(name, rows, out, st)
            for table, sql in inserts.items():
                conn.executemany(sql, out[table])
            total += len(rows)
            since_commit += len(rows)
            if since_commit >= COMMIT_ROWS:
                conn.execute("COMMIT")
                conn.execute("BEGIN")
                since_commit = 0
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return total


if __name__ == "__main__":
    run("etl", load_file, parse_args(__doc__))
