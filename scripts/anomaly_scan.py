"""
异常值全面扫描 — 修复一切不合理的数据
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

print("异常值全面扫描\n" + "=" * 55)

# ========== 1. 薪资异常值 ==========
print("\n[1] 薪资异常值")

# 总包极端值
cur.execute("""
    SELECT id, company, salary_base_monthly, salary_months,
           total_compensation, event_type,
           substr(evidence_text, 1, 80)
    FROM recruit_events
    WHERE total_compensation IS NOT NULL
    AND (total_compensation > 200 OR total_compensation < 5)
    ORDER BY total_compensation DESC
""")
anomaly_salary = cur.fetchall()
print(f"  总包异常 (>200w 或 <5w): {len(anomaly_salary)} 条")
for r in anomaly_salary:
    print(f"    ID:{r[0]} {r[1]:8s} {r[2] or '?'}k*{r[3] or '?'}={r[4]}w  {r[6][:50]}")

# base_monthly 极端值
cur.execute("""
    SELECT id, company, salary_base_monthly, salary_months,
           total_compensation, event_type,
           substr(evidence_text, 1, 80)
    FROM recruit_events
    WHERE salary_base_monthly IS NOT NULL
    AND (salary_base_monthly > 200 OR salary_base_monthly < 3)
    ORDER BY salary_base_monthly DESC
""")
anomaly_base = cur.fetchall()
print(f"  base_monthly 异常 (>200k 或 <3k): {len(anomaly_base)} 条")
for r in anomaly_base:
    print(f"    ID:{r[0]} {r[1]:8s} {r[2]}k  {r[6][:50]}")

# salary_months 异常值
cur.execute("""
    SELECT id, company, salary_base_monthly, salary_months,
           total_compensation, event_type,
           substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE salary_months IS NOT NULL
    AND (salary_months > 30 OR (salary_months > 20 AND salary_months != 2026 AND salary_months != 2025))
    ORDER BY salary_months DESC
""")
anomaly_months = cur.fetchall()
print(f"  salary_months 异常 (>20 且非年份): {len(anomaly_months)} 条")
for r in anomaly_months:
    print(f"    ID:{r[0]} {r[1]:8s} {r[2] or '?'}k*{r[3]}  {r[6][:50]}")

# ========== 2. 事件日期异常 ==========
print("\n[2] 事件日期异常")
from datetime import datetime
now = datetime.now()
cur.execute("""
    SELECT id, company, event_type, event_date, event_date_source,
           substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE event_date != ''
    ORDER BY event_date DESC
""")
all_dates = cur.fetchall()
future_dates = []
for r in all_dates:
    try:
        d = datetime.strptime(r[3][:10], "%Y-%m-%d")
        if d > now:
            future_dates.append(r)
    except:
        pass
print(f"  未来日期: {len(future_dates)} 条")
for r in future_dates[:5]:
    print(f"    ID:{r[0]} {r[1]:8s} {r[2]:15s} {r[3]}  {r[5][:50]}")

# ========== 3. 事件类型与证据不匹配 ==========
print("\n[3] 事件类型与证据不匹配")

# offer 事件但证据没有 positive 词
cur.execute("""
    SELECT id, company, event_type, substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE event_type = 'rejected'
    AND evidence_text LIKE '%Offer%'
    AND evidence_text NOT LIKE '%拒%'
    AND evidence_text NOT LIKE '%挂%'
    AND evidence_text NOT LIKE '%凉%'
    LIMIT 5
""")
print("  rejected 事件但含 Offer:")
for r in cur.fetchall():
    print(f"    ID:{r[0]} {r[1]:8s} {r[3][:60]}")

# ========== 4. 公司名为空或异常的帖子重新检查 ==========
print("\n[4] 其他异常")
cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE company = '' OR company IS NULL
""")
empty_company = cur.fetchone()[0]
print(f"  空公司名: {empty_company} 条")

cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE event_type = '' OR event_type IS NULL
""")
empty_type = cur.fetchone()[0]
print(f"  空事件类型: {empty_type} 条")

# 检查有没有 content_id 为空
cur.execute("SELECT COUNT(*) FROM recruit_events WHERE content_id = ''")
empty_cid = cur.fetchone()[0]
print(f"  空 content_id: {empty_cid} 条")

# 获取最终统计
cur.execute("SELECT COUNT(*) FROM recruit_events")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(DISTINCT company) FROM recruit_events")
companies = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM recruit_events WHERE salary_base_monthly IS NOT NULL")
has_salary = cur.fetchone()[0]

print(f"\n{'='*55}")
print(f"当前数据基线")
print(f"  事件总数: {total}")
print(f"  公司数: {companies}")
print(f"  薪资事件: {has_salary}")
print(f"  异常值总数(需修复): {len(anomaly_salary) + len(anomaly_months) + len(future_dates)}")

db.close()
