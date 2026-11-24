`title.basics`, 1,000,000 dòng, trung vị 3 lần chạy (nhỏ nhất – lớn nhất).

| Cấu hình | Giây | Dòng/giây | So với mốc |
|---|---:|---:|---:|
| Mốc so sánh: batch 10k, commit 1 lần, WAL + NORMAL | 1.65 (1.61 – 1.69) | 606,238 | 1.00x |
| Lô executemany: 100 dòng | 1.55 (1.54 – 1.55) | 646,224 | 1.07x |
| Lô executemany: 1.000 dòng | 1.60 (1.54 – 1.60) | 625,688 | 1.03x |
| Lô executemany: 100.000 dòng | 1.53 (1.39 – 1.65) | 655,067 | 1.08x |
| Lô executemany: 1 dòng (execute từng dòng, vẫn 1 transaction) | 2.11 (1.91 – 2.13) | 473,043 | 0.78x |
| Commit mỗi 100 dòng | 2.33 (2.25 – 2.43) | 428,382 | 0.71x |
| Commit mỗi 1.000 dòng | 1.72 (1.55 – 1.75) | 581,976 | 0.96x |
| Commit mỗi 10.000 dòng | 1.59 (1.37 – 1.63) | 628,372 | 1.04x |
| Commit mỗi 1.000 dòng, journal DELETE + FULL (mặc định của SQLite) | 9.34 (8.67 – 9.39) | 107,037 | 0.18x |
| Journal DELETE + FULL, commit 1 lần | 1.29 (1.26 – 1.46) | 775,935 | 1.28x |
| Journal OFF + sync OFF, commit 1 lần (không an toàn) | 1.14 (1.11 – 1.15) | 878,308 | 1.45x |
| Có index phụ, tạo TRƯỚC khi nạp | 3.48 (3.45 – 3.49) | 287,438 | 0.47x |
| Có index phụ, tạo SAU khi nạp | 2.43 (2.42 – 2.43) | 412,047 | 0.68x |
| Commit từng dòng, DELETE + FULL (chỉ 5.000 dòng) | 39.77 (39.68 – 40.27) | 126 | 0.00x |
