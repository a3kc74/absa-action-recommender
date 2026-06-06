from pathlib import Path
import duckdb

db = Path("data/local.duckdb")
rid = "pizza_4p_s_tòa_nhà_hoàng_thành_6a6686ffec"
month = "2026-04"
crawl_id = "crawl_d4ec138f4a064d09a2569192f6da873e"

con = duckdb.connect(str(db), read_only=True)

def show(title, query, params=None):
    print(f"\n## {title}")
    rows = con.execute(query, params or []).fetchall()
    print("count:", len(rows))
    for row in rows:
        print(row)

show(
    "crawl run 2026-04",
    "SELECT * FROM crawl_runs WHERE crawl_run_id=? OR target_month=? ORDER BY started_at",
    [crawl_id, month],
)

show(
    "reviews 2026-04 grouped by restaurant_id",
    "SELECT restaurant_id, COUNT(*) n, MIN(review_time), MAX(review_time), MIN(crawl_run_id), MAX(crawl_run_id) "
    "FROM reviews WHERE review_month=? GROUP BY restaurant_id ORDER BY n DESC",
    [month],
)

show(
    "reviews for crawl_d4ec... grouped by restaurant_id",
    "SELECT restaurant_id, review_month, COUNT(*) n, MIN(review_time), MAX(review_time) "
    "FROM reviews WHERE crawl_run_id=? GROUP BY restaurant_id, review_month ORDER BY n DESC",
    [crawl_id],
)

show(
    "restaurants active/target/peer for 2026-04 crawl restaurant ids",
    "SELECT r.restaurant_id, r.name, r.area_id, r.is_target, r.is_peer, r.status "
    "FROM restaurants r "
    "WHERE r.restaurant_id IN (SELECT DISTINCT restaurant_id FROM reviews WHERE crawl_run_id=?) "
    "ORDER BY r.is_target DESC, r.restaurant_id",
    [crawl_id],
)

show(
    "absa_annotations 2026-04 grouped by restaurant_id",
    "SELECT restaurant_id, COUNT(*) n, COUNT(DISTINCT review_id) review_n "
    "FROM absa_annotations WHERE review_month=? GROUP BY restaurant_id ORDER BY n DESC",
    [month],
)

show(
    "aspect_monthly_stats 2026-04 grouped by restaurant_id",
    "SELECT restaurant_id, COUNT(*) rows_n, SUM(mention_count) mentions, SUM(negative_count) negatives "
    "FROM aspect_monthly_stats WHERE review_month=? GROUP BY restaurant_id ORDER BY mentions DESC",
    [month],
)

show(
    "priority_items 2026-04 for target",
    "SELECT restaurant_id, review_month, rank, aspect, mention_count, negative_count, priority_score "
    "FROM priority_items WHERE restaurant_id=? AND review_month=? ORDER BY rank",
    [rid, month],
)

show(
    "target restaurant review ids 2026-04 exact",
    "SELECT review_id, restaurant_id, crawl_run_id, review_month, review_time, rating, LEFT(review_text, 120) "
    "FROM reviews WHERE restaurant_id=? AND review_month=? LIMIT 20",
    [rid, month],
)

con.close()