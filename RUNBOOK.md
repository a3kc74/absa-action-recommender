# RUNBOOK: Deploy và chạy hệ thống bằng Docker

Tài liệu này mô tả cách build, deploy và vận hành hệ thống `absa-action-recommender` bằng Docker/Docker Compose.

## 1. Tổng quan service

Repo hiện có các service Docker Compose sau:

| Service | Mục đích | Port/Profile |
|---|---|---|
| `api` | FastAPI backend | `8000` |
| `streamlit` | Dashboard Streamlit | `8501` |
| `monthly-run` | Job chạy pipeline một lần | profile `job` |
| `monthly-scheduler` | Scheduler chạy pipeline hàng tháng | profile `scheduler` |

Image dùng `python:3.12-slim`, cài dependency bằng `uv sync --frozen`, entrypoint mặc định là FastAPI.

## 2. Yêu cầu trước khi chạy

Cần cài:

- Docker Desktop
- Docker Compose v2

Kiểm tra:

```bash
docker --version
docker compose version
```

Repo cần có các thư mục/file sau:

```text
configs/
data/
models/
out/
docker-compose.yml
Dockerfile
pyproject.toml
```

Nếu thiếu `out`, tạo trước:

```bash
mkdir out
```

## 3. Dữ liệu, model và volume mount

Docker Compose mount các thư mục local vào container:

| Local | Container | Ý nghĩa |
|---|---|---|
| `./data` | `/app/data` | input reviews, DuckDB local |
| `./configs` | `/app/configs` | cấu hình runtime |
| `./models` | `/app/models` | model ABSA trained |
| `./out` | `/app/out` | output job pipeline |

Database mặc định:

```text
/app/data/local.duckdb
```

Output priority mặc định:

```text
/app/out/priority.json
```

Model trained mặc định cần có:

```text
models/acos_vit5_large_final.zip
```

Nếu không có model trained, không dùng `ABSA_ADAPTER=trained`; thay bằng `placeholder` hoặc `preannotated`.

## 4. Build image

Build toàn bộ service:

```bash
docker compose build
```

Build riêng API:

```bash
docker compose build api
```

Build lại không dùng cache:

```bash
docker compose build --no-cache
```

## 5. Chạy API và Streamlit dashboard

Chạy API + Streamlit foreground:

```bash
docker compose up api streamlit
```

Chạy background:

```bash
docker compose up -d api streamlit
```

Kiểm tra container:

```bash
docker compose ps
```

API:

```text
http://localhost:8000
```

Health check API:

```bash
curl http://localhost:8000/health
```

Streamlit dashboard:

```text
http://localhost:8501
```

Xem log:

```bash
docker compose logs -f api
docker compose logs -f streamlit
```

Dừng service:

```bash
docker compose down
```

## 6. Chạy monthly pipeline một lần

Service `monthly-run` dùng profile `job`.

Command mặc định trong Compose:

```bash
uv run absa-priority run-full \
  --input ${ABSA_INPUT_PATH:-/app/data/gmaps_monthly_raw.jsonl} \
  --restaurant-id ${ABSA_RESTAURANT_ID:-res_demo} \
  --month ${ABSA_REVIEW_MONTH:-2026-06} \
  --top-n ${ABSA_TOP_N:-10} \
  --absa-adapter ${ABSA_ADAPTER:-trained} \
  --source-adapter ${ABSA_SOURCE_ADAPTER:-google-maps} \
  --db-path /app/data/local.duckdb \
  --output /app/out/priority.json
```

Chạy với default:

```bash
docker compose --profile job run --rm monthly-run
```

Chạy cho restaurant/month cụ thể:

```bash
docker compose --profile job run --rm \
  -e ABSA_RESTAURANT_ID=res_demo \
  -e ABSA_REVIEW_MONTH=2026-06 \
  -e ABSA_TOP_N=10 \
  monthly-run
```

Chạy với adapter trained model:

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=trained \
  -e ABSA_SOURCE_ADAPTER=google-maps \
  monthly-run
```

Chạy với placeholder adapter để smoke test nhanh, không cần model trained:

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=placeholder \
  -e ABSA_SOURCE_ADAPTER=local \
  -e ABSA_INPUT_PATH=/app/data/samples/streamlit_priority_200.jsonl \
  monthly-run
```

Sau khi chạy, kiểm tra output:

```bash
dir out
```

Trên Linux/macOS:

```bash
ls -lah out
```

File chính:

```text
out/priority.json
```

## 7. Chạy pipeline local bằng `.venv` trong repo

Các lệnh dưới đây chạy trực tiếp trên máy local, không qua Docker. Phù hợp để debug crawler, Streamlit explore flow, hoặc chạy monthly pipeline nhanh trong repo.

> Windows PowerShell/CMD: dùng `.venv\Scripts\python.exe`.
> Linux/macOS: thay bằng `.venv/bin/python`.

### 7.1. Kiểm tra môi trường `.venv`

```bash
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pytest -q
```

Nếu Playwright chưa có browser Chromium:

```bash
.venv\Scripts\python.exe -m playwright install chromium
```

### 7.2. Chạy Streamlit dashboard local

```bash
.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

Dashboard local:

```text
http://localhost:8501
```

Streamlit app hiện chạy độc lập, không cần API để lưu dữ liệu. Khi bật `Load from DuckDB` và bấm `Run Explore`, app gọi trực tiếp Python pipeline trong repo:

```text
app/streamlit_app.py
  -> run_monthly_from_source(...)
  -> run_monthly_from_reviews(...)
  -> save_* vào DuckDB
```

Dữ liệu được lưu vào file DuckDB đang nhập ở sidebar `DuckDB path`, mặc định là:

```text
data/local.duckdb
```

Ngoài DuckDB, Google Maps raw crawl được ghi ra file:

```text
data/gmaps_streamlit_raw.jsonl
```

Vì vậy chạy mỗi Streamlit bằng `.venv` vẫn lưu được data local, miễn là:

- checkbox `Load from DuckDB` được bật;
- `DuckDB path` trỏ tới file local ghi được, ví dụ `data/local.duckdb`;
- bấm `Run Explore` để chạy crawl + ABSA + scoring pipeline;
- nếu dùng `ABSA adapter = trained` thì model `models/acos_vit5_large_final.zip` phải tồn tại.

API chỉ cần khi muốn expose backend HTTP; Streamlit dashboard local không phụ thuộc API cho flow Explore/persist DuckDB.

### 7.3. Smoke test monthly pipeline bằng sample local

Dùng `placeholder` adapter để kiểm tra nhanh, không cần model trained:

```bash
.venv\Scripts\python.exe -m absa_recommender.cli run-full ^
  --input data/samples/streamlit_priority_200.jsonl ^
  --restaurant-id res_demo ^
  --month 2026-06 ^
  --top-n 10 ^
  --absa-adapter placeholder ^
  --source-adapter local ^
  --db-path data/local.duckdb ^
  --output out/priority.json
```

### 7.4. Chạy monthly pipeline local với Google Maps JSONL và trained ABSA

Yêu cầu model tồn tại tại:

```text
models/acos_vit5_large_final.zip
```

Command:

```bash
.venv\Scripts\python.exe -m absa_recommender.cli run-full ^
  --input data/gmaps_monthly_raw.jsonl ^
  --restaurant-id res_demo ^
  --month 2026-06 ^
  --top-n 10 ^
  --absa-adapter trained ^
  --source-adapter google-maps ^
  --db-path data/local.duckdb ^
  --output out/priority.json
```

### 7.5. Crawl live Google Maps target restaurant để kiểm tra có review tháng `2026-05`

Ví dụ target: `Nhà hàng thượng hải 225 minh khai`.

```bash
.venv\Scripts\python.exe -m absa_recommender.sources.gmaps_url_crawler_single_discovery ^
  --live ^
  --target-url "https://www.google.com/maps/place/Nh%C3%A0+h%C3%A0ng+th%C6%B0%E1%BB%A3ng+h%E1%BA%A3i+225+minh+khai/@21.0073421,105.8270542,14z/data=!4m10!1m2!2m1!1zbmjDoCBow6BuZw!3m6!1s0x3135ad0001674a19:0x8e312879ead75127!8m2!3d20.9954534!4d105.8586423!15sCgpuaMOgIGjDoG5nWgwiCm5ow6AgaMOgbmeSAQpyZXN0YXVyYW50mgEkQ2hkRFNVaE5NRzluUzBWSmRYazBUV3BGY1hCWU9ITlJSUkFC4AEA-gEECAAQPA!16s%2Fg%2F11whz73h8k?entry=ttu&g_ep=EgoyMDI2MDYwMS4wIKXMDSoASAFQAw%3D%3D" ^
  --target-restaurant-name "Nhà hàng thượng hải 225 minh khai" ^
  --output data/tmp_target_gmaps_reviews.jsonl ^
  --crawl-month 2026-05 ^
  --crawl-time 2026-06-04T20:43:00+07:00 ^
  --mode collection ^
  --min-restaurants 1 ^
  --headful ^
  --max-reviews-per-restaurant 40 ^
  --stop-after-old-reviews 8 ^
  --include-unknown-time
```

Kiểm tra nhanh output:

```bash
.venv\Scripts\python.exe -c "import json,pathlib; p=pathlib.Path('data/tmp_target_gmaps_reviews.jsonl'); rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]; print(len(rows)); print(sorted({r.get('review_month') for r in rows})); print(sorted({r.get('restaurant_name') for r in rows}))"
```

### 7.6. Crawl live dạng Streamlit Explore: target + peer discovery trong ward

Config mẫu đã kiểm thử:

- Restaurant URL: `Nhà hàng thượng hải 225 minh khai`
- Crawl month: `2026-05`
- Ward/admin area: `Bạch Mai, Hà Nội, Việt Nam`
- Live Google Maps crawl: bật
- Discover peer restaurant in ward: bật
- ABSA adapter cho bước pipeline sau đó: `trained`

```bash
.venv\Scripts\python.exe -m absa_recommender.sources.gmaps_url_crawler_single_discovery ^
  --live ^
  --target-url "https://www.google.com/maps/place/Nh%C3%A0+h%C3%A0ng+th%C6%B0%E1%BB%A3ng+h%E1%BA%A3i+225+minh+khai/@21.0073421,105.8270542,14z/data=!4m10!1m2!2m1!1zbmjDoCBow6BuZw!3m6!1s0x3135ad0001674a19:0x8e312879ead75127!8m2!3d20.9954534!4d105.8586423!15sCgpuaMOgIGjDoG5nWgwiCm5ow6AgaMOgbmeSAQpyZXN0YXVyYW50mgEkQ2hkRFNVaE5NRzluUzBWSmRYazBUV3BGY1hCWU9ITlJSUkFC4AEA-gEECAAQPA!16s%2Fg%2F11whz73h8k?entry=ttu&g_ep=EgoyMDI2MDYwMS4wIKXMDSoASAFQAw%3D%3D" ^
  --target-restaurant-name "Nhà hàng thượng hải 225 minh khai" ^
  --discover-from-area ^
  --area-name "Bạch Mai, Hà Nội, Việt Nam" ^
  --search-query "nhà hàng Bạch Mai Hà Nội" ^
  --search-query "quán ăn Bạch Mai Hà Nội" ^
  --max-discovered-places 5 ^
  --output data/tmp_explore_streamlit_like_gmaps_reviews.jsonl ^
  --crawl-month 2026-05 ^
  --crawl-time 2026-06-04T20:43:00+07:00 ^
  --mode collection ^
  --min-restaurants 1 ^
  --headful ^
  --max-reviews-per-restaurant 40 ^
  --stop-after-old-reviews 8 ^
  --include-unknown-time
```

Kiểm tra số review và restaurant lấy được:

```bash
.venv\Scripts\python.exe -c "import json,pathlib; p=pathlib.Path('data/tmp_explore_streamlit_like_gmaps_reviews.jsonl'); rows=[json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]; print('reviews=', len(rows)); print('months=', sorted({r.get('review_month') for r in rows})); print('restaurants=', len({r.get('restaurant_id') for r in rows})); print(sorted({r.get('restaurant_name') for r in rows}))"
```

### 7.7. Chạy pipeline trained trên file vừa crawl

Sau khi có file crawl từ bước `7.5` hoặc `7.6`, chạy pipeline local:

```bash
.venv\Scripts\python.exe -m absa_recommender.cli run-full ^
  --input data/tmp_explore_streamlit_like_gmaps_reviews.jsonl ^
  --restaurant-id res_candidate_f4406cae ^
  --month 2026-05 ^
  --top-n 10 ^
  --absa-adapter trained ^
  --source-adapter google-maps ^
  --db-path data/local.duckdb ^
  --output out/priority_2026-05_bach_mai.json
```

Nếu chỉ cần smoke test không dùng trained model:

```bash
.venv\Scripts\python.exe -m absa_recommender.cli run-full ^
  --input data/tmp_explore_streamlit_like_gmaps_reviews.jsonl ^
  --restaurant-id res_candidate_f4406cae ^
  --month 2026-05 ^
  --top-n 10 ^
  --absa-adapter placeholder ^
  --source-adapter google-maps ^
  --db-path data/local.duckdb ^
  --output out/priority_2026-05_bach_mai_placeholder.json
```

### 7.8. Ghi chú debug crawler live

- Nếu mở URL Google Maps trực tiếp ra placeholder/search state, crawler sẽ cố dựng clean place URL từ Google feature id và tọa độ trong URL.
- Nếu discovery không thấy peer, thử query cụ thể hơn, ví dụ thêm ward/district: `"nhà hàng Bạch Mai Hà Nội"`.
- Chạy `--headful` khi debug để quan sát browser.
- Có thể giảm/tăng `--max-reviews-per-restaurant` và `--stop-after-old-reviews` tùy số review cần lấy.

## 8. Chạy scheduler hàng tháng

Service `monthly-scheduler` dùng profile `scheduler`.

Chạy foreground:

```bash
docker compose --profile scheduler up monthly-scheduler
```

Chạy background:

```bash
docker compose --profile scheduler up -d monthly-scheduler
```

Xem log scheduler:

```bash
docker compose logs -f monthly-scheduler
```

Dừng scheduler:

```bash
docker compose --profile scheduler stop monthly-scheduler
```

Xóa container scheduler:

```bash
docker compose --profile scheduler rm monthly-scheduler
```

## 9. Cấu hình lịch chạy

File cấu hình:

```text
configs/scheduler.yaml
```

Cấu hình hiện tại:

```yaml
monthly:
  enabled: true
  day_of_month: 3
  time_local: "03:00"
  process_previous_month: true
idempotency:
  key_fields:
    - restaurant_id
    - review_month
    - scoring_config_hash
    - absa_model_version
```

Ý nghĩa:

- `enabled: true`: bật scheduler.
- `day_of_month: 3`: chạy ngày 3 hằng tháng.
- `time_local: "03:00"`: chạy lúc 03:00 theo timezone/container local time.
- `process_previous_month: true`: tháng xử lý là tháng trước ngày chạy.

Ví dụ: nếu scheduler chạy ngày `2026-07-03`, pipeline xử lý month `2026-06`.

Compose hiện để scheduler chạy ngay một lần khi start bằng biến default:

```yaml
${ABSA_SCHEDULER_RUN_IMMEDIATELY:---run-immediately}
```

Muốn scheduler chỉ chờ đến lịch, không chạy ngay, set biến rỗng:

```bash
docker compose --profile scheduler run --rm \
  -e ABSA_SCHEDULER_RUN_IMMEDIATELY= \
  monthly-scheduler
```

## 10. Environment variables quan trọng

| Biến | Default | Ý nghĩa |
|---|---|---|
| `ABSA_DB_PATH` | `/app/data/local.duckdb` | đường dẫn DuckDB |
| `ABSA_INPUT_PATH` | `/app/data/gmaps_monthly_raw.jsonl` | input raw reviews |
| `ABSA_RESTAURANT_ID` | `res_demo` | restaurant target |
| `ABSA_REVIEW_MONTH` | `2026-06` | tháng xử lý cho `monthly-run` |
| `ABSA_TOP_N` | `10` | số priority item output |
| `ABSA_ADAPTER` | `trained` | ABSA adapter: `trained`, `vit5`, `placeholder`, `preannotated` |
| `ABSA_SOURCE_ADAPTER` | `google-maps` | source adapter: `google-maps`, `local` |
| `ABSA_SCHEDULER_RUN_IMMEDIATELY` | `--run-immediately` | scheduler có chạy ngay khi start không |

## 11. ABSA adapter

Các adapter hiện hỗ trợ:

### `trained` / `vit5`

Dùng model ViT5/ACOS trained từ:

```text
/app/models/acos_vit5_large_final.zip
```

Dùng khi có model zip trong `models/`.

Ví dụ:

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=trained \
  monthly-run
```

### `placeholder`

Rule-based adapter để smoke test/dev khi chưa có model.

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=placeholder \
  monthly-run
```

### `preannotated`

Input JSONL đã có annotations ABSA sẵn.

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=preannotated \
  monthly-run
```

## 12. Source adapter

### `google-maps`

Dùng Google Maps crawler adapter. Input mặc định:

```text
/app/data/gmaps_monthly_raw.jsonl
```

Chạy:

```bash
docker compose --profile job run --rm \
  -e ABSA_SOURCE_ADAPTER=google-maps \
  monthly-run
```

### `local`

Dùng file JSONL local, phù hợp cho smoke test.

```bash
docker compose --profile job run --rm \
  -e ABSA_SOURCE_ADAPTER=local \
  -e ABSA_INPUT_PATH=/app/data/samples/streamlit_priority_200.jsonl \
  monthly-run
```

## 13. Quy trình deploy khuyến nghị

### Bước 1: Chuẩn bị thư mục

```bash
mkdir out
```

### Bước 2: Đặt model

Đặt file model vào:

```text
models/acos_vit5_large_final.zip
```

### Bước 3: Build image

```bash
docker compose build
```

### Bước 4: Smoke test bằng placeholder

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=placeholder \
  -e ABSA_SOURCE_ADAPTER=local \
  -e ABSA_INPUT_PATH=/app/data/samples/streamlit_priority_200.jsonl \
  monthly-run
```

### Bước 5: Chạy pipeline thật bằng trained model

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=trained \
  -e ABSA_SOURCE_ADAPTER=google-maps \
  -e ABSA_RESTAURANT_ID=res_demo \
  -e ABSA_REVIEW_MONTH=2026-06 \
  monthly-run
```

### Bước 6: Start API/dashboard

```bash
docker compose up -d api streamlit
```

### Bước 7: Start scheduler

```bash
docker compose --profile scheduler up -d monthly-scheduler
```

## 14. Kiểm tra sau deploy

Kiểm tra service:

```bash
docker compose ps
```

Kiểm tra API health:

```bash
curl http://localhost:8000/health
```

Kiểm tra dashboard:

```text
http://localhost:8501
```

Kiểm tra output:

```bash
dir out
```

Kiểm tra logs:

```bash
docker compose logs -f api
docker compose logs -f streamlit
docker compose logs -f monthly-scheduler
```

## 15. Troubleshooting

### Trained model không tìm thấy

Lỗi thường gặp:

```text
Model zip not found: models/acos_vit5_large_final.zip
```

Cách xử lý:

- Đặt model zip vào `models/acos_vit5_large_final.zip`, hoặc
- Dùng adapter khác:

```bash
docker compose --profile job run --rm \
  -e ABSA_ADAPTER=placeholder \
  monthly-run
```

### Output không xuất hiện trong `out/`

Kiểm tra service `monthly-run` có mount:

```yaml
- ./out:/app/out
```

Tạo thư mục và chạy lại:

```bash
mkdir out
docker compose --profile job run --rm monthly-run
```

### API không thấy dữ liệu mới

API đọc database:

```text
/app/data/local.duckdb
```

Đảm bảo monthly job ghi cùng DB path:

```text
/app/data/local.duckdb
```

Sau khi job chạy xong, restart API nếu cần:

```bash
docker compose restart api
```

### Scheduler không chạy

Kiểm tra `configs/scheduler.yaml`:

```yaml
monthly:
  enabled: true
```

Xem log:

```bash
docker compose logs -f monthly-scheduler
```

Nếu log báo disabled, bật `enabled: true`.

### Muốn chạy scheduler ngay để kiểm thử

Default Compose đã truyền `--run-immediately`.

Chạy:

```bash
docker compose --profile scheduler up monthly-scheduler
```

### Muốn chạy scheduler nhưng không chạy ngay

```bash
docker compose --profile scheduler run --rm \
  -e ABSA_SCHEDULER_RUN_IMMEDIATELY= \
  monthly-scheduler
```

### Port 8000 hoặc 8501 bị chiếm

Đổi mapping trong `docker-compose.yml`, ví dụ:

```yaml
ports:
  - "8001:8000"
```

hoặc dừng process/container đang dùng port đó.

## 16. Lệnh dọn dẹp

Dừng toàn bộ service:

```bash
docker compose down
```

Dừng và xóa volume anonymous nếu có:

```bash
docker compose down -v
```

Xóa image build local:

```bash
docker compose down --rmi local
```

Xem disk usage Docker:

```bash
docker system df
```

Dọn cache build không dùng:

```bash
docker builder prune
```

## 17. Checklist vận hành production-like

- [ ] `docker compose build` thành công.
- [ ] `models/acos_vit5_large_final.zip` tồn tại nếu dùng `ABSA_ADAPTER=trained`.
- [ ] `configs/scheduler.yaml` đã đúng lịch chạy.
- [ ] `data/` được mount và persistent.
- [ ] `out/` được mount để lấy output.
- [ ] `api` health check OK tại `/health`.
- [ ] `streamlit` mở được tại `localhost:8501`.
- [ ] `monthly-run` chạy thành công ít nhất một lần.
- [ ] `monthly-scheduler` có log sleeping/ran đúng kỳ vọng.



# Extras
uv run app/streamlit_app.py --port 8051
