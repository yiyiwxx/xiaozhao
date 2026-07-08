"""排查误匹配的公司名"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 查 "班特别严重的"
cur.execute("""
    SELECT r.title, r.content
    FROM raw_records r
    JOIN recruit_events e ON e.content_id = r.content_id
    WHERE e.company = '班特别严重的'
""")
print("=== 班特别严重的 ===")
for row in cur.fetchall():
    print(f"Title: {row[0][:100]}")
    print(f"Content: {(row[1] or '')[:200]}")
    print()

# 查 "的科技"
cur.execute("""
    SELECT r.title, r.content
    FROM raw_records r
    JOIN recruit_events e ON e.content_id = r.content_id
    WHERE e.company = '的科技'
""")
print("=== 的科技 ===")
for row in cur.fetchall():
    print(f"Title: {row[0][:100]}")
    print(f"Content: {(row[1] or '')[:200]}")
    print()

# 查所有事件中公司名很短或者明显异常的
cur.execute("""
    SELECT company, COUNT(*) as cnt
    FROM recruit_events
    GROUP BY company
    ORDER BY cnt DESC
""")
print("=== 全部公司列表 ===")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

db.close()
