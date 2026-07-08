"""薪资改进验证"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 薪资提取总数
cur.execute("SELECT COUNT(*) FROM recruit_events WHERE salary_base_monthly IS NOT NULL")
has_base = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM recruit_events WHERE total_compensation IS NOT NULL")
has_tc = cur.fetchone()[0]

print(f"有 base_monthly: {has_base}")
print(f"有 total_compensation: {has_tc}")

# 新增的那些
print("\n放宽后新增捕获的薪资:")
cur.execute("""
    SELECT company, salary_base_monthly, salary_months, total_compensation,
           substr(evidence_text, 1, 80)
    FROM recruit_events
    WHERE salary_base_monthly IS NOT NULL
    ORDER BY salary_base_monthly DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:8s} {str(r[1] or '?'):>5s}k * {str(r[2] or '?'):>2s}  = {str(r[3] or '?'):>5s}w  {r[4][:50]}")

# 公司列表
cur.execute("SELECT company, COUNT(*) FROM recruit_events GROUP BY company ORDER BY cnt DESC")
print("\n公司列表:")
for r in cur.fetchall():
    print(f"  {r[0]:12s} {r[1]}")

db.close()
