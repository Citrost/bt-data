# Báo cáo: nạp dữ liệu IMDb vào database nhiều bảng bằng Python

## 1. Tóm tắt

- Dữ liệu: 7 file IMDb, **217.227.269 dòng**, file nào cũng trên 1 triệu dòng.
- Nạp **93.633.496 dòng nguồn** thành **168.933.133 dòng** trong 15 bảng SQLite, bằng hai cách.
- Hai cách cho **dữ liệu giống nhau** (mục 5).
- Khi máy ổn định, **ETL nhanh hơn khoảng 11%** ở bản lớn (651 so với 733 giây) và nhanh hơn ở cả 5 cặp mẫu nhỏ.
- **ELT dùng ít RAM hơn khoảng 23%** (399 so với 518 MB).
- Yếu tố ảnh hưởng mạnh nhất không phải là chọn ETL hay ELT mà là **số lần commit kết hợp với chế độ journal** (mục 6).

## 2. Dữ liệu

Nguồn: [IMDb Non-Commercial Datasets](https://developer.imdb.com/non-commercial-datasets), tải ngày 2026-11-24.
Số dòng do `src/inspect_data.py` đếm trực tiếp, không có dòng nào sai số cột.

| File | Số dòng | Nạp vào DB | Sinh ra các bảng |
|---|---:|---:|---|
| title.basics | 12.997.011 | Tất cả | titles, title_types, genres, title_genres |
| name.basics | 15.839.664 | Tất cả | names, professions, name_professions, name_known_titles |
| title.ratings | 1.735.902 | Tất cả | title_ratings |
| title.episode | 10.063.908 | Tất cả | episodes |
| title.crew | 12.997.011 | Tất cả | title_directors, title_writers |
| title.akas | 60.649.816 | 20 triệu dòng đầu | title_akas |
| title.principals | 102.943.957 | 20 triệu dòng đầu | title_principals, categories |

Hai file cuối bị giới hạn vì dung lượng ổ đĩa. Các cột danh sách (`genres`, `directors`, `knownForTitles`...) được tách
thành bảng nối, nên số dòng ghi vào DB nhiều hơn số dòng nguồn.

Quy tắc làm sạch (giống nhau ở hai cách):
- `\N` thành `NULL`.
- `tt0000001` / `nm0000001` lưu thành số nguyên.
- Bỏ dòng trỏ tới phim hoặc người không có trong bảng cha, và bỏ cặp trùng trong bảng nối.
  Ví dụ ở bản lớn, `episodes` bị bỏ 7 dòng và `title_principals` bị bỏ 140 dòng. Các bảng nối (tách từ danh sách) chưa đếm riêng số cặp bị bỏ.

## 3. Hai cách

**Cách 1 - ETL** ([method1_etl_batch.py](src/method1_etl_batch.py)): Python đọc từng dòng, tách cột, ép kiểu, lọc dòng mồ côi,
rồi `executemany` vào bảng đích theo lô 10.000 dòng nguồn. Để lọc mồ côi, script giữ hai bitmap id trong RAM (200 MB).

**Cách 2 - ELT** ([method2_elt_staging.py](src/method2_elt_staging.py)): Python đổ nguyên văn vào bảng staging tạm
(toàn TEXT, không ràng buộc, nằm trong RAM), mỗi lượt 500.000 dòng. SQLite tự tách (`json_each`), ép kiểu và lọc
bằng `INSERT ... SELECT`.

Giữ giống nhau: schema, khóa ngoại bật, WAL + `synchronous = NORMAL`, cache 256 MB, commit mỗi 500.000 dòng nguồn,
cùng cách đọc gzip.

## 4. Kết quả

Máy: i5-12450H, RAM 16 GB, ổ D: SSD NVMe Samsung, Windows 11 (chế độ nguồn Balanced), Python 3.13.12, SQLite 3.51.1.
Thời gian tính từ lúc bắt đầu đọc file đầu tiên đến khi checkpoint xong.

### Bản lớn (93,6 triệu dòng nguồn)

Cặp B chạy lúc máy ổn định:

| File | ETL (giây) | ELT (giây) | ETL nhanh hơn |
|---|---:|---:|---:|
| title.basics | 93,0 | 108,9 | 15% |
| name.basics | 206,0 | 225,5 | 9% |
| title.ratings | 5,8 | 6,2 | 6% |
| title.episode | 40,4 | 47,1 | 14% |
| title.crew | 96,7 | 124,5 | 22% |
| title.akas | 96,2 | 106,7 | 10% |
| title.principals | 113,1 | 114,3 | 1% |
| **Tổng** | **651,3** | **733,2** | **11%** |
| Tốc độ (dòng nguồn/giây) | 143.771 | 127.700 | |
| RAM đỉnh | 518 MB | 399 MB | ELT thấp hơn 23% |
| Kích thước DB | 4.241 MB | 4.253 MB | |

Các lần chạy khác:

| Lần | Thứ tự | ETL | ELT | Ghi chú |
|---|---|---:|---:|---|
| Cặp A | ETL trước | 1.097,7 | 1.061,1 | Tốc độ máy thay đổi giữa chừng, **không dùng để kết luận** |
| Lượt lẻ | ELT | - | 724,8 | Lượt ETL đi kèm chạy cùng lúc với một game nên bị dừng và bỏ |
| Cặp B | ELT trước | 651,3 | 733,2 | Dùng để kết luận |

### Mẫu nhỏ (1 triệu dòng mỗi file, 7 triệu dòng nguồn)

| Cặp | ETL (giây) | ELT (giây) | ETL ít hơn |
|---|---:|---:|---:|
| 1 | 67,9 | 79,2 | 14% |
| 2 | 63,0 | 76,7 | 18% |
| 3 | 43,9 | 75,9 | 42% (máy đổi tốc độ, không tin cậy) |
| 4 | 38,0 | 46,2 | 18% |
| 5 | 37,9 | 45,1 | 16% |

Cặp 1–3 chạy lúc máy chậm, cặp 4–5 lúc máy nhanh. Thời gian tuyệt đối vì vậy không so được giữa các cặp,
nhưng chiều chênh lệch giống nhau ở cả 5 cặp.

## 5. Đối chiếu dữ liệu

- **Mẫu 7 triệu dòng:** so từng dòng của cả 15 bảng bằng `EXCEPT` hai chiều, 0 khác biệt. `foreign_key_check`: 0 lỗi.
- **Bản lớn:** so số dòng và tổng kiểm tra (tổng id, tổng độ dài chuỗi, số ô khác NULL) của cả 15 bảng, khớp hết.
  Chưa so từng dòng ở quy mô này.

## 6. Yếu tố nào ảnh hưởng?

`title.basics`, 1 triệu dòng, mỗi cấu hình 3 lần chạy trên DB mới, mỗi lần chỉ đổi một yếu tố. Số gốc:
[ablation.md](results/ablation.md) (lần 2, máy ổn định hơn) và [ablation_run1.md](results/ablation_run1.md) (lần 1).

| Cấu hình | Dòng/giây | So với mốc |
|---|---:|---:|
| Mốc: lô 10k, 1 transaction, WAL + NORMAL | 606.238 | 1,00x |
| Lô 100 đến 100.000 dòng | 626–655 nghìn | khoảng 1,03–1,08x |
| `execute` từng dòng, 1 transaction | 473.043 | 0,78x |
| Commit mỗi 100 dòng, WAL | 428.382 | 0,71x |
| Commit mỗi 1.000 dòng, WAL | 581.976 | 0,96x |
| Commit mỗi 1.000 dòng, DELETE + FULL (mặc định SQLite) | 107.037 | **0,18x** |
| Commit từng dòng, DELETE + FULL (chỉ 5.000 dòng) | 126 | 0,0002x |
| Tạo index trước khi nạp | 287.438 | 0,47x |
| Tạo index sau khi nạp | 412.047 | 0,68x |
| Journal OFF + sync OFF (không an toàn) | 878.308 | 1,45x |

- **Commit + journal là yếu tố lớn nhất.** Với cấu hình mặc định, commit mỗi 1.000 dòng chậm hơn mốc 5,7 lần.
- **Kích thước lô gần như không ảnh hưởng** từ 100 dòng trở lên (nằm trong mức nhiễu).
- **Tạo index sau khi nạp** nhanh hơn tạo trước.
- Lần 1 và lần 2 có thứ tự giống nhau ở các yếu tố lớn. Trong một cấu hình, các lần chạy chênh nhau tới khoảng 20% (lần 1 rõ nhất),
  nên đừng tin các chênh lệch nhỏ. DELETE + FULL commit một lần và Journal OFF cho kết quả khác nhau giữa hai lần
  (0,94x / 1,28x và 1,05x / 1,45x), nên không kết luận.

## 7. Ưu nhược điểm

| | ETL (xử lý trong Python) | ELT (staging + SQL) |
|---|---|---|
| Tốc độ | Nhanh hơn 9–22% ở 5/7 file của cặp B | Gần bằng ở `title.ratings` và `title.principals` (6% và 1%) |
| RAM | Cao hơn (giữ bitmap id) | Thấp hơn |
| Xử lý phức tạp | Dễ viết, dễ debug từng dòng bằng Python | Phải viết bằng SQL, biểu thức dài |
| Kiểm tra lại | Khó xem dữ liệu gốc sau khi nạp | Có thể giữ staging để kiểm tra dữ liệu thô |
| Khi đổi quy tắc | Sửa Python và nạp lại từ file | Có thể chạy lại SQL từ staging (nếu giữ staging) |
| Chuyển sang DB khác | Gần như giữ nguyên Python | Phải viết lại SQL (`json_each` là của SQLite) |

Chọn ETL khi làm sạch phức tạp, theo từng dòng. Chọn ELT khi cần xử lý lại nhiều lần hoặc muốn DB làm phần việc theo tập hợp.

## 8. Giới hạn

- Tốc độ máy thay đổi giữa các lần chạy (chế độ nguồn Balanced, có lúc đang chạy game). Nên đọc kết quả theo từng cặp,
  không so thời gian tuyệt đối giữa các cặp.
- Bản lớn mới có **một cặp đáng tin** (cặp B). Con số 11% chưa có khoảng dao động, nên xem là ước lượng.
- `title.akas` và `title.principals` chỉ nạp 20 triệu dòng đầu. File được sắp theo id nên phần này không đại diện cho cả file.
- Chưa chạy thử với toàn bộ 217 triệu dòng.
- Kết quả đúng với SQLite trên máy này, có thể khác ở DB khác (ví dụ PostgreSQL có `COPY`).
