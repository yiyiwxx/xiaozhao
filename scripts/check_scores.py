"""验证评分数据"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 查看综合评分最高的10条事件
cur.execute("""
    SELECT company, event_type, quality_score, relevance_score,
           validity_score, composite_score,
           substr(evidence_text, 1, 50) as evidence
    FROM recruit_events
    WHERE composite_score > 0
    ORDER BY composite_score DESC
    LIMIT 10
""")
print(f"{'公司':10s} {'事件':12s} {'质量':>5s} {'相关':>5s} {'有效':>5s} {'综合':>5s}  证据")
print("-" * 80)
for r in cur.fetchall():
    print(f"{r[0]:10s} {r[1]:12s} {r[2]:5.0f} {r[3]:5.0f} {r[4]:5.0f} {r[5]:5.0f}  {r[6][:50]}")

# 查看综合评分分布
print("\n=== 综合评分分布 ===")
cur.execute("""
    SELECT
        CASE
            WHEN composite_score >= 80 THEN '80-100 ⭐⭐'
            WHEN composite_score >= 60 THEN '60-79  ⭐'
            WHEN composite_score >= 40 THEN '40-59  参考'
            WHEN composite_score >= 20 THEN '20-39  低'
            ELSE '0-19   噪音'
        END as tier,
        COUNT(*) as cnt
    FROM recruit_events
    GROUP BY tier
    ORDER BY tier
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}条")

# 查看产品岗位 + 高评分事件
print("\n=== 产品岗位高评分事件 ===")
cur.execute("""
    SELECT company, role, event_type, composite_score,
           substr(evidence_text, 1, 60) as evidence
    FROM recruit_events
    WHERE role_category = '产品' AND composite_score >= 50
    ORDER BY composite_score DESC
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r[0]:8s} | {r[1]:10s} | {r[2]:12s} | 评分:{r[3]:5.1f} | {r[4][:50]}")

db.close()
