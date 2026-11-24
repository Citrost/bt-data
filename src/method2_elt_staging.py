"""Cách 2 - ELT: đổ nguyên văn vào bảng staging (toàn TEXT, không ràng buộc),
sau đó SQL tự tách/ép kiểu/lọc bằng INSERT ... SELECT theo tập hợp.

Ví dụ: python src/method2_elt_staging.py --limit 1000000 --tag small
"""
from __future__ import annotations

import sqlite3

from common import COMMIT_ROWS, chunks, parse_args, read_rows, run

COLUMNS = {
    "title.basics": "tconst,ttype,ptitle,otitle,adult,syear,eyear,runtime,genres",
    "name.basics": "nconst,pname,byear,dyear,professions,known",
    "title.ratings": "tconst,rating,votes",
    "title.episode": "tconst,parent,season,episode",
    "title.crew": "tconst,directors,writers",
    "title.akas": "tconst,ordering,title,region,language,types,attributes,original",
    "title.principals": "tconst,ordering,nconst,category,job,characters",
}


def pk(col: str) -> str:  # 'tt0000001' -> 1
    return f"CAST(substr({col}, 3) AS INTEGER)"


def num(col: str) -> str:
    return f"CASE WHEN {col} GLOB '[0-9]*' AND {col} NOT GLOB '*[^0-9]*' THEN CAST({col} AS INTEGER) END"


def text(col: str) -> str:
    return f"NULLIF({col}, '\\N')"


def split(col: str) -> str:  # 'a,b,c' -> 3 dòng
    return f"json_each('[\"' || replace({col}, ',', '\",\"') || '\"]') AS j"


def exists(table: str, key: str, expr: str) -> str:
    return f"EXISTS (SELECT 1 FROM {table} WHERE {key} = {expr})"


J = pk("j.value")
HAS_T = exists("titles", "title_id", pk("s.tconst"))


def lookup_split(table: str, col: str) -> str:
    # GROUP BY trước để chỉ phải tách vài trăm/nghìn tổ hợp khác nhau thay vì 500k dòng.
    return (f"INSERT OR IGNORE INTO {table}(name) SELECT DISTINCT j.value FROM "
            f"(SELECT {col} AS v FROM stg WHERE {col} <> '\\N' GROUP BY {col}) s, {split('s.v')}")


def lookup(table: str, col: str) -> str:
    return f"INSERT OR IGNORE INTO {table}(name) SELECT DISTINCT {col} FROM stg"


def crew(table: str, col: str) -> str:
    return (f"INSERT OR IGNORE INTO {table} SELECT {pk('s.tconst')}, {J} FROM stg s, {split('s.' + col)} "
            f"WHERE s.{col} <> '\\N' AND {HAS_T} AND {exists('names', 'name_id', J)}")


TRANSFORMS = {
    "title.basics": [
        lookup("title_types", "ttype"),
        lookup_split("genres", "genres"),
        f"INSERT INTO titles SELECT {pk('tconst')}, (SELECT type_id FROM title_types WHERE name = ttype), "
        f"ptitle, otitle, CAST(adult AS INTEGER), {num('syear')}, {num('eyear')}, {num('runtime')} FROM stg",
        f"INSERT OR IGNORE INTO title_genres SELECT {pk('s.tconst')}, "
        f"(SELECT genre_id FROM genres WHERE name = j.value) "
        f"FROM stg s, {split('s.genres')} WHERE s.genres <> '\\N'"],
    "name.basics": [
        lookup_split("professions", "professions"),
        f"INSERT INTO names SELECT {pk('nconst')}, {text('pname')}, {num('byear')}, {num('dyear')} FROM stg",
        f"INSERT OR IGNORE INTO name_professions SELECT {pk('s.nconst')}, "
        f"(SELECT profession_id FROM professions WHERE name = j.value) "
        f"FROM stg s, {split('s.professions')} WHERE s.professions <> '\\N'",
        f"INSERT OR IGNORE INTO name_known_titles SELECT {pk('s.nconst')}, {J} FROM stg s, {split('s.known')} "
        f"WHERE s.known <> '\\N' AND {exists('titles', 'title_id', J)}"],
    "title.ratings": [
        f"INSERT INTO title_ratings SELECT {pk('s.tconst')}, CAST(rating AS REAL), CAST(votes AS INTEGER) "
        f"FROM stg s WHERE {HAS_T}"],
    "title.episode": [
        f"INSERT INTO episodes SELECT {pk('s.tconst')}, {pk('s.parent')}, {num('season')}, {num('episode')} FROM stg s "
        f"WHERE {HAS_T} AND {exists('titles', 'title_id', pk('s.parent'))}"],
    "title.crew": [crew("title_directors", "directors"), crew("title_writers", "writers")],
    "title.akas": [
        f"INSERT INTO title_akas SELECT {pk('s.tconst')}, CAST(ordering AS INTEGER), title, {text('region')}, "
        f"{text('language')}, {text('types')}, {text('attributes')}, {num('original')} FROM stg s WHERE {HAS_T}"],
    "title.principals": [
        lookup("categories", "category"),
        f"INSERT INTO title_principals SELECT {pk('s.tconst')}, CAST(ordering AS INTEGER), {pk('s.nconst')}, "
        f"(SELECT category_id FROM categories WHERE name = s.category), {text('job')}, {text('characters')} "
        f"FROM stg s WHERE {HAS_T} AND {exists('names', 'name_id', pk('s.nconst'))}"],
}


def load_file(conn: sqlite3.Connection, name: str, limit: int | None, st: dict) -> int:
    cols = COLUMNS[name].split(",")
    # TEMP + temp_store=MEMORY: staging nằm trong RAM, mỗi lượt chỉ chứa COMMIT_ROWS dòng.
    conn.execute("DROP TABLE IF EXISTS temp.stg")
    conn.execute(f"CREATE TEMP TABLE stg ({', '.join(c + ' TEXT' for c in cols)})")
    load_sql = f"INSERT INTO stg VALUES ({','.join('?' * len(cols))})"
    rows_iter = read_rows(name, limit)
    total = 0
    done = False
    while not done:
        conn.execute("BEGIN")
        try:
            # E + L: đổ nguyên văn theo lô 10k (để không giữ cả 500k list trong RAM)
            loaded = 0
            for _ in range(COMMIT_ROWS // 10_000):
                batch = next(chunks(rows_iter, 10_000), None)
                if batch is None:
                    done = True
                    break
                conn.executemany(load_sql, batch)
                loaded += len(batch)
            if loaded:
                for sql in TRANSFORMS[name]:  # T: theo tập hợp, trong SQL
                    conn.execute(sql)
                conn.execute("DELETE FROM stg")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        total += loaded
    return total


if __name__ == "__main__":
    run("elt", load_file, parse_args(__doc__))
