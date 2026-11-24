# IMDb Bulk Insert: so sánh ETL và ELT (Python + SQLite)

Nạp 7 file IMDb vào một database SQLite 15 bảng bằng hai cách khác nhau về cơ chế:

| | Cách 1: ETL | Cách 2: ELT |
|---|---|---|
| Script | `src/method1_etl_batch.py` | `src/method2_elt_staging.py` |
| Xử lý dữ liệu ở đâu | Python: tách cột, ép kiểu, lọc dòng mồ côi | SQL: trên bảng staging |
| Ghi vào bảng đích | `executemany`, lô 10.000 dòng nguồn | `INSERT ... SELECT`, lượt 500.000 dòng nguồn |
| Giống nhau | Schema, PRAGMA, khóa ngoại bật, commit mỗi 500.000 dòng nguồn | |

Kết quả, ưu nhược điểm và giới hạn của phép đo: xem [REPORT.md](REPORT.md).

## Dữ liệu

[IMDb Non-Commercial Datasets](https://developer.imdb.com/non-commercial-datasets), 7 file `.tsv.gz`, khoảng 2 GB nén.
Mỗi file đều có hơn 1 triệu dòng ([số đếm thật](results/row_counts.md)). IMDb cập nhật hằng ngày, nên số dòng
khi bạn tải sẽ khác một chút. Dữ liệu chỉ dùng cho mục đích cá nhân, phi thương mại và **không** được push lên GitHub.

> Information courtesy of IMDb (https://www.imdb.com). Used with permission.

## Yêu cầu

- Python 3.10 trở lên. Không cần cài thêm thư viện.
- SQLite 3.38 trở lên, đi kèm Python (kiểm tra: `python -c "import sqlite3; print(sqlite3.sqlite_version)"`).
- Ổ đĩa trống khoảng 12 GB nếu giữ cả hai DB bản lớn.

## Cách chạy

Chạy từ thư mục `bt-data/`.

```bash
# 1. Tải dữ liệu
python src/download_data.py

# 2. (Tùy chọn) Đếm dòng, kiểm tra file
python src/inspect_data.py

# 3. Chạy thử nhanh: 1 triệu dòng mỗi file
python src/method1_etl_batch.py --limit 1000000 --tag small
python src/method2_elt_staging.py --limit 1000000 --tag small
python src/verify.py small

# 4. Bản lớn: 93,6 triệu dòng nguồn
python src/method1_etl_batch.py --limit-akas 20000000 --limit-principals 20000000 --tag full
python src/method2_elt_staging.py --limit-akas 20000000 --limit-principals 20000000 --tag full
python src/verify.py full

# 5. Thí nghiệm đổi từng yếu tố
python src/ablation.py
```

- Bỏ hai cờ `--limit-*` để nạp toàn bộ 217 triệu dòng (chưa chạy thử ở quy mô này).
- DB nằm ở `data/db/<cách>_<tag>.db`. Script **từ chối ghi đè** DB cũ: hãy đổi `--tag` hoặc tự xóa file.
- Thêm `--drop-db` để xóa DB vừa tạo sau khi đo.

## Cấu trúc

```text
bt-data/
├── README.md, REPORT.md
├── sql/schema.sql               # 15 bảng
├── src/
│   ├── download_data.py         # tải dữ liệu
│   ├── inspect_data.py          # đếm dòng, kiểm tra cột
│   ├── common.py                # phần dùng chung của hai cách
│   ├── method1_etl_batch.py     # Cách 1
│   ├── method2_elt_staging.py   # Cách 2
│   ├── verify.py                # đối chiếu dữ liệu hai cách
│   └── ablation.py              # đổi từng yếu tố một
├── results/                     # số đo gốc (JSON, Markdown)
└── data/                        # dữ liệu và DB (không push)
```
