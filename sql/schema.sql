-- 15 bảng, sinh từ 7 file IMDb. tconst 'tt0000001' và nconst 'nm0000001' được lưu thành số nguyên.

-- Bảng tra cứu (tách từ các cột lặp lại)
CREATE TABLE title_types (type_id       INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE genres      (genre_id      INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE professions (profession_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE categories  (category_id   INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);

-- title.basics -> titles + title_types + genres + title_genres
CREATE TABLE titles (
    title_id        INTEGER PRIMARY KEY,
    type_id         INTEGER NOT NULL REFERENCES title_types(type_id),
    primary_title   TEXT NOT NULL,
    original_title  TEXT NOT NULL,
    is_adult        INTEGER NOT NULL,
    start_year      INTEGER,
    end_year        INTEGER,
    runtime_minutes INTEGER
);
CREATE TABLE title_genres (
    title_id INTEGER NOT NULL REFERENCES titles(title_id),
    genre_id INTEGER NOT NULL REFERENCES genres(genre_id),
    PRIMARY KEY (title_id, genre_id)
) WITHOUT ROWID;

-- name.basics -> names + professions + name_professions + name_known_titles
CREATE TABLE names (
    name_id      INTEGER PRIMARY KEY,
    primary_name TEXT,
    birth_year   INTEGER,
    death_year   INTEGER
);
CREATE TABLE name_professions (
    name_id       INTEGER NOT NULL REFERENCES names(name_id),
    profession_id INTEGER NOT NULL REFERENCES professions(profession_id),
    PRIMARY KEY (name_id, profession_id)
) WITHOUT ROWID;
CREATE TABLE name_known_titles (
    name_id  INTEGER NOT NULL REFERENCES names(name_id),
    title_id INTEGER NOT NULL REFERENCES titles(title_id),
    PRIMARY KEY (name_id, title_id)
) WITHOUT ROWID;

-- title.ratings -> title_ratings
CREATE TABLE title_ratings (
    title_id       INTEGER PRIMARY KEY REFERENCES titles(title_id),
    average_rating REAL NOT NULL,
    num_votes      INTEGER NOT NULL
);

-- title.episode -> episodes
CREATE TABLE episodes (
    title_id  INTEGER PRIMARY KEY REFERENCES titles(title_id),
    parent_id INTEGER NOT NULL REFERENCES titles(title_id),
    season    INTEGER,
    episode   INTEGER
);

-- title.crew -> title_directors + title_writers
CREATE TABLE title_directors (
    title_id INTEGER NOT NULL REFERENCES titles(title_id),
    name_id  INTEGER NOT NULL REFERENCES names(name_id),
    PRIMARY KEY (title_id, name_id)
) WITHOUT ROWID;
CREATE TABLE title_writers (
    title_id INTEGER NOT NULL REFERENCES titles(title_id),
    name_id  INTEGER NOT NULL REFERENCES names(name_id),
    PRIMARY KEY (title_id, name_id)
) WITHOUT ROWID;

-- title.akas -> title_akas
CREATE TABLE title_akas (
    title_id    INTEGER NOT NULL REFERENCES titles(title_id),
    ordering    INTEGER NOT NULL,
    title       TEXT NOT NULL,
    region      TEXT,
    language    TEXT,
    types       TEXT,
    attributes  TEXT,
    is_original INTEGER,
    PRIMARY KEY (title_id, ordering)
) WITHOUT ROWID;

-- title.principals -> title_principals + categories
CREATE TABLE title_principals (
    title_id    INTEGER NOT NULL REFERENCES titles(title_id),
    ordering    INTEGER NOT NULL,
    name_id     INTEGER NOT NULL REFERENCES names(name_id),
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    job         TEXT,
    characters  TEXT,
    PRIMARY KEY (title_id, ordering)
) WITHOUT ROWID;
