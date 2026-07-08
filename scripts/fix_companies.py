"""清理误匹配的公司事件并重解析"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 列出已知误匹配
bad_companies = ['班特别严重的', '的科技', '去本地', '说是要等其他']

for bad in bad_companies:
    cur.execute("DELETE FROM recruit_events WHERE company = ?", (bad,))
    print(f"删除了 {cur.rowcount} 条 '{bad}' 事件")

db.conn.commit()
db.close()

# 重解析（用新的 pipeline 实例）
from crawler.pipeline import Pipeline
p = Pipeline(CRAWL_CONFIG['db_path'])
p.run_parse()
p.close()
