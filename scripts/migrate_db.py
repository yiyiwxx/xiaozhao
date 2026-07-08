"""为 recruit_events 表添加三层评分字段"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 检查字段是否已存在
cur.execute("PRAGMA table_info(recruit_events)")
existing = {r[1] for r in cur.fetchall()}

new_fields = [
    ("quality_score", "REAL DEFAULT 0"),
    ("relevance_score", "REAL DEFAULT 0"),
    ("validity_score", "REAL DEFAULT 0"),
    ("composite_score", "REAL DEFAULT 0"),
]

for field_name, field_type in new_fields:
    if field_name not in existing:
        cur.execute(f"ALTER TABLE recruit_events ADD COLUMN {field_name} {field_type}")
        print(f"已添加字段: {field_name}")

# 检查 raw_records 是否有 detail_url
cur2 = db.conn.cursor()
cur2.execute("PRAGMA table_info(raw_records)")
raw_cols = {r[1] for r in cur2.fetchall()}
if "detail_url" not in raw_cols:
    cur2.execute("ALTER TABLE raw_records ADD COLUMN detail_url TEXT DEFAULT ''")
    print("已添加字段: raw_records.detail_url")

db.conn.commit()
db.close()
print("数据库迁移完成")
