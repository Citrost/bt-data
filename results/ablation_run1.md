`title.basics`, 1,000,000 dòng, trung vị 3 lần chạy (nhỏ nhất – lớn nhất).

| Cấu hình | Giây | Dòng/giây | So với mốc |
|---|---:|---:|---:|
| Mốc so sánh: batch 10k, commit 1 lần, WAL + NORMAL | 2.01 (1.66 – 2.42) | 498,621 | 1.00x |
| Lô executemany: 100 dòng | 2.55 (2.45 – 2.73) | 392,655 | 0.79x |
| Lô executemany: 1.000 dòng | 2.43 (2.38 – 2.44) | 411,169 | 0.82x |
| Lô executemany: 100.000 dòng | 2.44 (2.31 – 2.63) | 409,672 | 0.82x |
| Lô executemany: 1 dòng (execute từng dòng, vẫn 1 transaction) | 3.72 (3.60 – 4.28) | 268,800 | 0.54x |
| Commit mỗi 100 dòng | 3.67 (3.49 – 3.71) | 272,145 | 0.55x |
| Commit mỗi 1.000 dòng | 2.72 (2.65 – 3.06) | 368,040 | 0.74x |
| Commit mỗi 10.000 dòng | 2.59 (2.48 – 2.89) | 386,116 | 0.77x |
| Commit mỗi 1.000 dòng, journal DELETE + FULL (mặc định của SQLite) | 12.09 (12.04 – 12.25) | 82,722 | 0.17x |
| Journal DELETE + FULL, commit 1 lần | 2.13 (2.00 – 2.19) | 469,718 | 0.94x |
| Journal OFF + sync OFF, commit 1 lần (không an toàn) | 1.90 (1.75 – 2.05) | 525,535 | 1.05x |
| Có index phụ, tạo TRƯỚC khi nạp | 5.90 (5.71 – 6.03) | 169,414 | 0.34x |
| Có index phụ, tạo SAU khi nạp | 3.89 (3.77 – 3.99) | 256,761 | 0.51x |
| Commit từng dòng, DELETE + FULL (chỉ 5.000 dòng) | 46.26 (45.53 – 49.52) | 108 | 0.00x |
