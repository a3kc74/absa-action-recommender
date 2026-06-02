Dưới đây là pipeline mới theo hướng **Aspect Priority Recommender**, kế thừa phần ABSA, severity, aggregation, priority scoring, API, dashboard và DuckDB từ báo cáo hiện tại, nhưng **loại bỏ hoàn toàn sub-problem detection và action recommendation**. Báo cáo hiện tại đang có schema ABSA, mapping `aspect_category → aspect`, `opinion_expression → opinion_text`, severity scoring, aggregation, priority scoring, API/Streamlit/DuckDB; các phần subproblem/action sẽ được gỡ khỏi pipeline mới. 

## 1. Mục tiêu hệ thống mới

Hệ thống mới chỉ làm 3 việc chính:

1. Thu thập review theo tháng cho một nhà hàng mục tiêu và các nhà hàng peer trong cùng khu vực.
2. Infer review qua mô hình ABSA để lấy annotation dạng `aspect_expression`, `aspect_category`, `opinion_expression`, `sentiment`, `model_confidence`.
3. Tính `priority_score` theo từng aspect và trả về **Top-N aspect cần cải thiện** cho nhà hàng mục tiêu trong tháng hiện tại, kèm dashboard giải thích vì sao aspect đó được ưu tiên.

Tên hệ thống nên đổi từ:

```text
Aspect-to-Action Recommender
```

thành:

```text
Restaurant Aspect Priority Recommender
```

hoặc:

```text
ABSA Aspect Priority Engine
```

## 2. Kiến trúc tổng thể mới

```text
Google Maps / licensed review source
        ↓
Monthly Crawler / Source Adapter
        ↓
Raw Review Normalizer + Deduplication
        ↓
Review Storage
        ↓
ABSA Inference Service
        ↓
Annotation Storage
        ↓
Severity Scoring
        ↓
Monthly Aspect Aggregation
        ↓
Peer Benchmark + Trend Computation
        ↓
Priority Scoring Engine
        ↓
Top-N Aspect Ranking
        ↓
FastAPI + Streamlit Dashboard + Scheduled Monthly Runs
```

Với phần Google Maps, nên thiết kế dưới dạng **source adapter** thay vì hardcode crawler. Lý do là Google Maps Platform có các ràng buộc về scraping, caching, lưu nội dung, attribution và việc sử dụng Google Maps Content; Terms hiện tại nêu “No Scraping” và ví dụ không được copy/save business names, addresses hoặc user reviews ngoài phạm vi được phép. ([Google Cloud][1]) Vì vậy nên ưu tiên Places API, Business Profile API nếu phù hợp quyền sở hữu nhà hàng, hoặc một nguồn review có license rõ ràng. Places API có Nearby Search để tìm địa điểm theo vùng và yêu cầu field mask cho dữ liệu trả về. ([Google for Developers][2]) Place IDs có thể lưu để truy xuất lại sau, nhưng Google cũng khuyến nghị refresh Place ID nếu quá 12 tháng. ([Google for Developers][3]) Nếu hiển thị Google Maps content trên dashboard, cần attribution Google Maps rõ ràng theo chính sách Places API. ([Google for Developers][4])

## 3. Các module chính cần có

| Module                           | Vai trò                                                                   |
| -------------------------------- | ------------------------------------------------------------------------- |
| `crawler/`                       | Lấy review theo tháng cho target restaurant và peer restaurants.          |
| `sources/google_maps_adapter.py` | Adapter riêng cho Google Maps hoặc API hợp pháp.                          |
| `peer_discovery.py`              | Tìm các nhà hàng peer trong bán kính hoặc khu vực cấu hình.               |
| `review_normalizer.py`           | Chuẩn hóa review thành schema nội bộ.                                     |
| `dedup.py`                       | Chống trùng review bằng `source_review_id`, hash text, rating, thời gian. |
| `absa_inference.py`              | Chạy model ABSA để sinh annotations.                                      |
| `severity.py`                    | Giữ logic severity hiện tại.                                              |
| `aggregation.py`                 | Aggregate theo `restaurant_id`, `month`, `aspect`.                        |
| `benchmark.py`                   | Tính peer average, peer percentile, benchmark gap.                        |
| `trend.py`                       | Tính xu hướng tháng hiện tại so với tháng trước hoặc rolling window.      |
| `priority.py`                    | Tính `priority_score`.                                                    |
| `ranking.py`                     | Sắp xếp Top-N aspect cần cải thiện.                                       |
| `scheduler.py`                   | Chạy pipeline tự động khi sang tháng mới.                                 |
| `storage.py`                     | DuckDB tables cho review, annotations, monthly stats, priority runs.      |
| `api.py`                         | FastAPI endpoints cho dashboard và batch run.                             |
| `streamlit_app.py`               | Dashboard cho chủ nhà hàng.                                               |

## 4. Pipeline end-to-end mới

### Bước 1: Cấu hình nhà hàng mục tiêu

Input ban đầu:

```yaml
target_restaurant:
  internal_restaurant_id: "res_001"
  google_place_id: "..."
  restaurant_name: "..."
  area:
    center_lat: 10.77
    center_lng: 106.69
    radius_meters: 1500
  peer_filters:
    included_types: ["restaurant"]
    min_rating: 0
    max_peers: 30
```

Hệ thống cần lưu `google_place_id` hoặc source-specific place id để crawl định kỳ. Không nên dùng tên nhà hàng làm khóa chính vì tên có thể thay đổi hoặc trùng.

### Bước 2: Discover peer restaurants

Mỗi tháng hoặc mỗi quý, hệ thống chạy peer discovery:

```text
Input: target place_id, tọa độ, bán kính, loại địa điểm
Output: danh sách peer restaurant trong khu vực
```

Peer restaurant nên được lọc theo:

| Tiêu chí                                  | Mục đích                                          |
| ----------------------------------------- | ------------------------------------------------- |
| Cùng loại hình: restaurant, cafe, quán ăn | Tránh benchmark sai với khách sạn, siêu thị, bar. |
| Trong bán kính cấu hình                   | So sánh cùng khu vực cạnh tranh.                  |
| Có đủ review mới hoặc tổng review         | Tránh peer quá ít dữ liệu.                        |
| Không phải chính target                   | Không tự benchmark với mình.                      |
| Có trạng thái hoạt động hợp lệ            | Tránh nhà hàng đã đóng cửa.                       |

Output bảng `restaurants`:

```text
restaurant_id
source
source_place_id
name
lat
lng
area_id
is_target
is_peer
first_seen_at
last_seen_at
status
```

### Bước 3: Crawl review theo tháng

Mỗi run có `target_month`, ví dụ `2026-06`.

Crawler lấy review của:

```text
1 target restaurant
N peer restaurants trong cùng area
```

Review sau khi lấy về được normalize:

```json
{
  "source": "google_maps",
  "source_place_id": "...",
  "source_review_id": "...",
  "restaurant_id": "res_001",
  "review_text": "...",
  "rating": 3,
  "review_time": "2026-06-14T10:30:00",
  "fetched_at": "2026-07-01T03:00:00",
  "review_month": "2026-06",
  "language": "vi"
}
```

Cần có `retention_policy` theo nguồn dữ liệu:

```yaml
source_policy:
  google_maps:
    raw_text_retention: "check_license"
    allow_dashboard_snippets: false
    allow_absa_training: false
    require_attribution: true
  licensed_provider:
    raw_text_retention: "per_contract"
    allow_dashboard_snippets: true
    allow_absa_training: true
```

Điểm quan trọng: với Google Maps, không nên mặc định lưu raw review lâu dài, hiển thị snippet, hoặc dùng dữ liệu để train/fine-tune model nếu chưa xác nhận quyền sử dụng. Terms hiện tại cũng có điều khoản không dùng Google Maps Content để improve, train, test, validate hoặc fine-tune ML/AI models. ([Google Cloud][1]) Thiết kế an toàn hơn là dùng model ABSA đã train sẵn để inference, lưu metric tổng hợp nếu được phép, và tách rõ phần dữ liệu có license.

### Bước 4: Dedup và lưu review

Dedup theo thứ tự ưu tiên:

```text
1. source_review_id nếu có
2. hash(source_place_id + normalized_review_text + rating + review_time)
3. fuzzy duplicate nếu review_time thiếu hoặc text gần giống
```

Bảng `reviews`:

```text
review_id
source
source_place_id
restaurant_id
review_text
review_text_hash
rating
review_time
review_month
fetched_at
language
is_duplicate
crawl_run_id
```

### Bước 5: ABSA inference

Mỗi review được đưa vào model ABSA để sinh annotation:

```json
{
  "review_id": "...",
  "restaurant_id": "res_001",
  "rating": 3,
  "review_time": "2026-06-14T10:30:00",
  "annotations": [
    {
      "aspect_expression": "phở bò",
      "aspect_category": "Food Quality",
      "opinion_expression": "không đậm đà",
      "sentiment": "negative",
      "model_confidence": 0.91
    }
  ]
}
```

Mapping nội bộ giữ như báo cáo hiện tại:

```text
aspect_category     → aspect
aspect_expression   → aspect_term
opinion_expression  → opinion_text
```

Không dùng field `evidence`.

Bảng `absa_annotations`:

```text
annotation_id
review_id
restaurant_id
review_month
aspect
aspect_term
opinion_text
sentiment
model_confidence
severity
absa_model_version
created_at
```

### Bước 6: Tính severity

Giữ logic severity hiện tại:

```text
positive → severity = 0.0
neutral  → base severity = 0.25
negative → base severity = 0.75
strong negative pattern → severity cao hơn
Food Safety hoặc safety pattern → severity rất cao
```

Severity vẫn bị clamp trong `[0, 1]`. Phần này giữ lại vì rất hữu ích cho priority score: một aspect có ít complaint nhưng complaint rất nghiêm trọng vẫn cần được đẩy lên cao.

### Bước 7: Aggregate theo tháng, nhà hàng, aspect

Khóa aggregate mới:

```text
restaurant_id + review_month + aspect
```

Bảng `aspect_monthly_stats`:

```text
restaurant_id
review_month
aspect
mention_count
negative_count
positive_count
neutral_count
negative_rate_raw
negative_rate_smoothed
avg_severity
avg_rating
avg_confidence
mention_share
rating_gap
total_mentions_for_restaurant
window_start
window_end
```

Công thức cơ bản:

```text
mention_count = số annotation của aspect đó
negative_count = số annotation negative
positive_count = số annotation positive
neutral_count = số annotation neutral

negative_rate_raw = negative_count / mention_count

avg_severity = mean(severity)
avg_rating = mean(rating)
avg_confidence = mean(model_confidence)

mention_share = log(1 + mention_count) / log(1 + total_mentions_for_restaurant)

rating_gap = (5 - avg_rating) / 4
```

Với negative rate, tiếp tục dùng Bayesian smoothing:

```text
p_hat = (negative_count + alpha * global_aspect_negative_rate) 
        / (mention_count + alpha)
```

Trong hệ thống mới, `global_aspect_negative_rate` nên lấy từ dữ liệu nhiều tháng hoặc toàn bộ khu vực, không chỉ từ batch hiện tại. Như vậy aspect ít mention sẽ không bị score quá nhiễu.

### Bước 8: Tính peer benchmark

Với mỗi `area_id`, `review_month`, `aspect`, tính peer stats từ các nhà hàng peer, loại target ra khỏi tập peer.

Bảng `peer_aspect_monthly_stats`:

```text
area_id
target_restaurant_id
review_month
aspect
peer_restaurant_count
peer_total_mentions
peer_negative_count
peer_negative_rate
peer_avg_severity
peer_avg_rating
peer_p50_negative_rate
peer_p75_negative_rate
peer_p90_negative_rate
peer_support_confidence
```

Công thức benchmark gap:

```text
benchmark_gap = clamp(
    (target_negative_rate_smoothed - peer_negative_rate) / benchmark_scale,
    0,
    1
)
```

Gợi ý:

```yaml
benchmark:
  min_peer_restaurants: 5
  min_peer_mentions_per_aspect: 20
  benchmark_scale: 0.30
```

Nếu peer data không đủ:

```text
benchmark_gap = 0
peer_support_flag = "low_peer_support"
```

Nhưng dashboard vẫn phải hiển thị rõ: “Không đủ dữ liệu peer cho aspect này”.

### Bước 9: Tính trend score

Trend giúp phát hiện aspect đang xấu đi trong tháng hiện tại.

So sánh tháng hiện tại `t` với tháng trước `t-1` hoặc rolling window 3 tháng:

```text
negative_trend = clamp(
    (p_hat_t - p_hat_previous) / trend_negative_scale,
    0,
    1
)

severity_trend = clamp(
    (avg_severity_t - avg_severity_previous) / trend_severity_scale,
    0,
    1
)

trend_score = 0.7 * negative_trend + 0.3 * severity_trend
```

Gợi ý config:

```yaml
trend:
  mode: "previous_month"   # hoặc rolling_3_months
  negative_scale: 0.25
  severity_scale: 0.30
  min_mentions_current: 5
  min_mentions_previous: 5
```

Nếu tháng trước thiếu dữ liệu:

```text
trend_score = 0
trend_flag = "insufficient_history"
```

### Bước 10: Tính priority_score

Công thức chính giữ tinh thần báo cáo cũ, nhưng bây giờ `trend_score` và `benchmark_gap` không còn là fallback 0 nữa vì hệ thống đã có dữ liệu theo tháng và peer.

Với nhà hàng `r`, aspect `a`, tháng `t`:

```text
x = (
  negative_rate_smoothed,
  avg_severity,
  mention_share,
  rating_gap,
  trend_score,
  benchmark_gap
)
```

```text
priority_score = 100 * clamp(
    risk_multiplier[aspect] * Σ(w_i * x_i),
    0,
    1
)
```

Config gợi ý:

```yaml
weights:
  negative_rate: 0.25
  sentiment_severity: 0.18
  mention_share: 0.12
  rating_gap: 0.12
  trend_score: 0.16
  benchmark_gap: 0.17

risk_multiplier:
  Food Safety: 1.20
  Cleanliness: 1.10
  Food Quality: 1.00
  Service: 1.00
  Price: 1.00
  Ambience: 1.00
  Location: 0.95
  Menu: 1.00
  Unknown: 0.70
```

So với báo cáo cũ, có thể giảm nhẹ `rating_gap` và tăng `benchmark_gap`, vì giờ hệ thống đã có peer data thật.

### Bước 11: Tính confidence cho priority

Không nên chỉ trả `priority_score`, vì chủ nhà hàng cần biết score đó đáng tin tới đâu.

```text
support_confidence = 1 - exp(-mention_count / tau)

model_confidence = avg_confidence

peer_confidence = clamp(peer_total_mentions / peer_support_tau, 0, 1)

history_confidence = 1 nếu có đủ dữ liệu trend, ngược lại 0.5 hoặc 0
```

```text
priority_confidence =
  0.45 * support_confidence +
  0.30 * model_confidence +
  0.15 * peer_confidence +
  0.10 * history_confidence
```

Output nên có cả:

```text
priority_score
priority_confidence
data_quality_flags
```

Ví dụ flags:

```text
low_mentions
low_peer_support
insufficient_history
low_model_confidence
missing_review_time
```

### Bước 12: Top-N aspect ranking

Output mới không còn `sub_problem_id`, `recommended_actions`, `monitoring_kpis`.

Schema mới:

```json
{
  "restaurant_id": "res_001",
  "restaurant_name": "Nhà hàng A",
  "review_month": "2026-06",
  "generated_at": "2026-07-01T03:30:00",
  "top_n": 5,
  "items": [
    {
      "rank": 1,
      "aspect": "Cleanliness",
      "priority_score": 82.4,
      "priority_confidence": 0.78,
      "severity": 0.88,
      "mention_count": 42,
      "negative_count": 25,
      "negative_rate_smoothed": 0.57,
      "mention_share": 0.31,
      "rating_gap": 0.42,
      "trend_score": 0.65,
      "benchmark_gap": 0.48,
      "risk_multiplier": 1.10,
      "component_scores": {
        "negative_rate": 0.57,
        "sentiment_severity": 0.88,
        "mention_share": 0.31,
        "rating_gap": 0.42,
        "trend_score": 0.65,
        "benchmark_gap": 0.48
      },
      "peer_summary": {
        "peer_restaurant_count": 18,
        "peer_negative_rate": 0.22,
        "target_vs_peer_gap": 0.35
      },
      "trend_summary": {
        "previous_month_priority_score": 61.2,
        "priority_delta": 21.2,
        "negative_rate_delta": 0.19
      },
      "opinion_examples": [
        "bàn hơi bẩn",
        "nhà vệ sinh có mùi"
      ],
      "data_quality_flags": []
    }
  ]
}
```

Với `Food Safety`, nên giữ rule cũ ở mức aspect:

```yaml
ranking:
  force_food_safety_top3: true
  food_safety_negative_threshold: 0.10
```

Nhưng giờ item chỉ là aspect `Food Safety`, không còn sub-problem/action.

## 5. Dashboard frontend nên có gì

Dashboard nên tập trung giải thích **vì sao một aspect được ưu tiên**, không chỉ hiển thị rank.

### Tab 1: Monthly Overview

Hiển thị cho tháng hiện tại:

| Metric                     | Ý nghĩa                                  |
| -------------------------- | ---------------------------------------- |
| Total reviews              | Số review crawl được trong tháng.        |
| Total ABSA annotations     | Số annotation sau inference.             |
| Average rating             | Rating trung bình tháng hiện tại.        |
| Negative annotation rate   | Tỷ lệ annotation negative toàn nhà hàng. |
| Number of peer restaurants | Số peer dùng để benchmark.               |
| Data freshness             | Lần crawl cuối.                          |
| ABSA model version         | Version model đang dùng.                 |
| Scoring config hash        | Đảm bảo audit được score.                |

Plot nên có:

```text
- Line chart: review_count theo tháng
- Line chart: avg_rating theo tháng
- Bar chart: số mention theo aspect trong tháng hiện tại
- Stacked bar: sentiment distribution theo aspect
```

### Tab 2: Top-N Aspects to Improve

Bảng chính:

| Rank | Aspect | Priority | Confidence | Negative rate | Severity | Trend | Peer gap |
| ---- | -----: | -------: | ---------: | ------------: | -------: | ----: | -------: |

Mỗi aspect có expandable panel:

```text
- Component contribution
- Vì sao score cao
- So với tháng trước
- So với peer
- Opinion examples nếu source policy cho phép
- Data quality flags
```

Plot nên có:

```text
- Horizontal bar chart: priority_score theo aspect
- Waterfall hoặc stacked bar: đóng góp từng component vào priority_score
```

### Tab 3: Aspect Detail

Khi chọn một aspect, hiển thị:

```text
Aspect: Cleanliness
Priority score: 82.4
Rank: #1
Confidence: 0.78
```

Plot:

```text
- Trend line: priority_score 6 tháng gần nhất
- Trend line: negative_rate 6 tháng gần nhất
- Trend line: avg_severity 6 tháng gần nhất
- Bar chart: target negative_rate vs peer average vs peer P75
- Histogram hoặc boxplot: phân phối peer negative_rate cho aspect đó
- Sentiment ratio: positive / neutral / negative
```

Phần giải thích:

```text
Aspect này được ưu tiên vì:
- Negative rate cao hơn peer average 35 điểm phần trăm.
- Severity trung bình tăng so với tháng trước.
- Mention share lớn, tức nhiều khách đang nhắc đến.
- Risk multiplier cao vì thuộc nhóm Cleanliness.
```

### Tab 4: Peer Benchmark

Hiển thị theo từng aspect:

| Aspect | Target negative rate | Peer avg | Peer P75 | Target percentile |
| ------ | -------------------: | -------: | -------: | ----------------: |

Plot:

```text
- Grouped bar chart: target vs peer average theo aspect
- Heatmap: aspect × month cho benchmark_gap
```

### Tab 5: History

Cho phép chọn tháng cũ:

```text
review_month = 2026-03, 2026-04, 2026-05, 2026-06
```

Hiển thị lại đúng snapshot của tháng đó, không tính lại bằng config mới trừ khi user chọn “recompute”.

Cần lưu:

```text
scoring_config_hash
absa_model_version
crawl_run_id
priority_run_id
generated_at
```

để dashboard tháng cũ có tính audit.

### Tab 6: Data Quality & Crawl Status

Hiển thị:

```text
- Crawl success / failed restaurants
- Số review mới
- Số duplicate
- Số review không có review_time
- Số annotation confidence thấp
- Số aspect thiếu peer benchmark
- Last successful scheduled run
```

## 6. DuckDB schema đề xuất

Thay các bảng cũ liên quan subproblem/action bằng bảng mới.

### `restaurants`

```text
restaurant_id
source
source_place_id
name
lat
lng
area_id
is_target
is_peer
status
first_seen_at
last_seen_at
```

### `crawl_runs`

```text
crawl_run_id
source
target_month
area_id
started_at
finished_at
status
num_restaurants
num_reviews_fetched
num_reviews_inserted
num_duplicates
error_message
```

### `reviews`

```text
review_id
crawl_run_id
restaurant_id
source
source_review_id
review_text
review_text_hash
rating
review_time
review_month
language
fetched_at
```

### `absa_annotations`

```text
annotation_id
review_id
restaurant_id
review_month
aspect
aspect_term
opinion_text
sentiment
model_confidence
severity
absa_model_version
created_at
```

### `aspect_monthly_stats`

```text
restaurant_id
review_month
aspect
mention_count
negative_count
positive_count
neutral_count
negative_rate_raw
negative_rate_smoothed
avg_severity
avg_rating
avg_confidence
mention_share
rating_gap
total_mentions_for_restaurant
```

### `peer_aspect_monthly_stats`

```text
area_id
target_restaurant_id
review_month
aspect
peer_restaurant_count
peer_total_mentions
peer_negative_rate
peer_avg_severity
peer_avg_rating
peer_p50_negative_rate
peer_p75_negative_rate
peer_p90_negative_rate
peer_support_confidence
```

### `priority_runs`

```text
priority_run_id
restaurant_id
review_month
generated_at
crawl_run_id
absa_model_version
scoring_config_hash
status
```

### `priority_items`

```text
priority_run_id
restaurant_id
review_month
rank
aspect
priority_score
priority_confidence
severity
mention_count
negative_count
negative_rate_smoothed
mention_share
rating_gap
trend_score
benchmark_gap
risk_multiplier
component_scores_json
peer_summary_json
trend_summary_json
opinion_examples_json
data_quality_flags_json
```

## 7. API mới

Bỏ các endpoint:

```text
POST /api/v1/subproblems/locate
POST /api/v1/taxonomy/mine
POST /api/v1/recommendations/{id}/feedback nếu feedback action không còn cần
```

Giữ hoặc thêm:

```text
GET  /health
GET  /api/v1/labels
POST /api/v1/crawl/run
POST /api/v1/absa/infer
POST /api/v1/priority/run
POST /api/v1/monthly/run
GET  /api/v1/restaurants/{restaurant_id}/priority?month=2026-06&top_n=5
GET  /api/v1/restaurants/{restaurant_id}/dashboard?month=2026-06
GET  /api/v1/restaurants/{restaurant_id}/history
GET  /api/v1/restaurants/{restaurant_id}/aspects/{aspect}/history
GET  /api/v1/restaurants/{restaurant_id}/peer-benchmark?month=2026-06
```

## 8. CLI mới

```bash
uv run absa-priority discover-peers \
  --restaurant-id res_001 \
  --radius-meters 1500

uv run absa-priority crawl-month \
  --restaurant-id res_001 \
  --month 2026-06

uv run absa-priority infer-absa \
  --month 2026-06

uv run absa-priority compute-stats \
  --restaurant-id res_001 \
  --month 2026-06

uv run absa-priority score-priority \
  --restaurant-id res_001 \
  --month 2026-06 \
  --top-n 5

uv run absa-priority run-monthly \
  --restaurant-id res_001 \
  --month 2026-06 \
  --top-n 5

uv run absa-priority backfill \
  --restaurant-id res_001 \
  --start-month 2026-01 \
  --end-month 2026-06
```

## 9. Scheduling khi qua tháng mới

Không cần Airflow nếu muốn giữ local-first. Có thể dùng:

```text
cron + Typer CLI
```

hoặc:

```text
APScheduler trong service FastAPI
```

Lịch gợi ý:

```text
Ngày 1 hàng tháng, 03:00:
- chạy crawl cho tháng vừa kết thúc
- infer ABSA
- compute monthly stats
- compute peer benchmark
- compute trend
- generate priority run
- refresh dashboard cache
```

Nên chạy cho tháng vừa kết thúc thay vì tháng mới:

```text
2026-07-01 → process review_month = 2026-06
```

Có thể delay 1–3 ngày để tránh review cuối tháng cập nhật trễ:

```text
Ngày 3 hàng tháng, 03:00
```

Scheduler phải idempotent:

```text
same restaurant_id + same month + same config hash + same model version
→ không tạo duplicate run, chỉ update nếu force=true
```

## 10. Monitoring cần thêm

Bỏ monitoring cho subproblem/action. Thay bằng monitoring cho dữ liệu, ABSA và scoring.

| Metric                           | Ý nghĩa                                   |
| -------------------------------- | ----------------------------------------- |
| `crawl_success_rate`             | Tỷ lệ crawl thành công.                   |
| `reviews_fetched_count`          | Số review lấy được.                       |
| `new_review_count`               | Review mới sau dedup.                     |
| `duplicate_rate`                 | Tỷ lệ duplicate.                          |
| `missing_review_time_rate`       | Tỷ lệ review thiếu thời gian.             |
| `absa_inference_failure_rate`    | Tỷ lệ infer lỗi.                          |
| `low_confidence_annotation_rate` | Tỷ lệ annotation confidence thấp.         |
| `aspect_coverage`                | Aspect nào có đủ dữ liệu.                 |
| `peer_support_rate`              | Tỷ lệ aspect có đủ peer benchmark.        |
| `priority_score_stability`       | Độ ổn định rank qua rerun.                |
| `dashboard_data_freshness`       | Dashboard có đang dùng dữ liệu mới không. |

Alert gợi ý:

```text
crawl_success_rate < 90% → kiểm tra crawler/API quota
peer_support_rate < 70% → peer quá ít hoặc area quá hẹp
missing_review_time_rate > 30% → trend theo tháng có thể không tin cậy
low_confidence_annotation_rate > 25% → kiểm tra ABSA model
priority_score thay đổi > 30 điểm sau rerun cùng dữ liệu → kiểm tra config/model hash
```

## 11. Config files mới

Giữ:

```text
configs/label_schema.yaml
configs/severity_lexicon.yaml
configs/scoring.yaml
```

Thêm:

```text
configs/crawler.yaml
configs/peer_discovery.yaml
configs/scheduler.yaml
configs/absa_model.yaml
configs/dashboard.yaml
configs/source_policy.yaml
```

Bỏ:

```text
configs/subproblem_rules.yaml
configs/subproblem_prototypes.yaml
configs/locator.yaml
configs/action_catalog.yaml
```

`scoring.yaml` mới nên có:

```yaml
weights:
  negative_rate: 0.25
  sentiment_severity: 0.18
  mention_share: 0.12
  rating_gap: 0.12
  trend_score: 0.16
  benchmark_gap: 0.17

smoothing:
  alpha: 10

confidence:
  support_threshold_tau: 30
  peer_support_tau: 100
  weights:
    support: 0.45
    model: 0.30
    peer: 0.15
    history: 0.10

trend:
  mode: previous_month
  negative_scale: 0.25
  severity_scale: 0.30
  min_mentions_current: 5
  min_mentions_previous: 5

benchmark:
  min_peer_restaurants: 5
  min_peer_mentions_per_aspect: 20
  benchmark_scale: 0.30

ranking:
  force_food_safety_top3: true
  food_safety_negative_threshold: 0.10
```

## 12. Kết luận thiết kế

Pipeline mới nên được hiểu là:

```text
Monthly Google/Review Data
→ ABSA Annotations
→ Severity
→ Monthly Aspect Stats
→ Trend + Peer Benchmark
→ Priority Score
→ Top-N Aspects
→ Dashboard + Historical Runs
```

Điểm khác biệt cốt lõi so với hệ thống cũ là:

| Hệ thống cũ                       | Hệ thống mới                                                         |
| --------------------------------- | -------------------------------------------------------------------- |
| Recommend action                  | Recommend aspect priority                                            |
| Có sub-problem detection          | Bỏ hoàn toàn                                                         |
| Có action catalog                 | Bỏ hoàn toàn                                                         |
| Trend/benchmark là MVP fallback 0 | Trend/benchmark là component chính nhờ crawl theo tháng và peer data |
| Streamlit hiển thị action card    | Streamlit hiển thị dashboard phân tích aspect                        |
| Output là recommendation item     | Output là ranked aspect item                                         |
| Taxonomy mining cho subproblem    | Không cần, chỉ cần label schema và ABSA quality monitoring           |

Thiết kế này phù hợp hơn với mục tiêu mới: chủ nhà hàng không nhận “hành động mẫu” nữa, mà nhận một danh sách **Top-N aspect cần cải thiện**, có score, confidence, xu hướng theo tháng, và so sánh với các nhà hàng xung quanh.

[1]: https://cloud.google.com/maps-platform/terms "Google Maps Platform Terms Of Service | Google Cloud"
[2]: https://developers.google.com/maps/documentation/places/web-service/nearby-search "Nearby Search (New)  |  Places API  |  Google for Developers"
[3]: https://developers.google.com/maps/documentation/places/web-service/place-id "Place IDs  |  Places API  |  Google for Developers"
[4]: https://developers.google.com/maps/documentation/places/web-service/policies "Policies and attributions for Places API  |  Google for Developers"
