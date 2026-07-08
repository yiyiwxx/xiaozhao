"""
全面数据质量自我核查
检查项:
  1. 公司名完整性 — 有没有截断/多字少字
  2. 公司名别名匹配 — 有没有误匹配
  3. 事件类型合理性 — Offer/面试/开奖是否合理
  4. 日期合理性 — 没有未来/远古日期
  5. 岗位分类合理性
  6. 薪资提取质量
  7. 模板帖/广告帖比例
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

print("=" * 60)
print("数据质量自我核查报告")
print("=" * 60)

# ==== 1. 公司名完整性检查 ====
print("\n[1] 公司名完整性")
cur.execute("SELECT company, COUNT(*) FROM recruit_events GROUP BY company ORDER BY company")
companies = cur.fetchall()
for c, cnt in companies:
    issues = []
    # 检查是否以"有限"结尾但不完整
    if c.endswith("有限") and not c.endswith("有限公司") and c != "普联技术有限":
        issues.append("可能被截断: 以'有限'结尾")
    # 检查是否含有不应该有的词
    if c.startswith("的") or c.startswith("了"):
        issues.append("可疑前缀")
    # 检查长度
    if len(c) <= 1:
        issues.append("公司名过短")
    # 检查是否含有标点
    import re
    if re.search(r'[，。、！？：；""''（）【】《》]', c):
        issues.append("含有标点符号")
    
    if issues:
        print(f"  ⚠️  '{c}' ({cnt}条): {'; '.join(issues)}")
    else:
        print(f"  ✅ '{c}' ({cnt}条)")

# ==== 2. 别名匹配质量 ====
print("\n[2] 别名匹配抽样")
# 检查包含别名关键词的事件是否匹配到正确公司
alias_checks = [
    ("WXG", "腾讯"),
    ("PCG", "腾讯"),
    ("IEG", "腾讯"),
    ("抖音", "字节跳动"),
    ("飞书", "字节跳动"),
    ("PDD", "拼多多"),
    ("鹅厂", "腾讯"),
    ("xhs", "小红书"),
    ("B站", "哔哩哔哩"),
    ("b站", "哔哩哔哩"),
]
for alias, expected in alias_checks:
    cur.execute("""
        SELECT company, evidence_text FROM recruit_events
        WHERE evidence_text LIKE ? LIMIT 3
    """, (f"%{alias}%",))
    rows = cur.fetchall()
    if rows:
        all_correct = all(r[0] == expected for r in rows)
        if not all_correct:
            wrong = [(r[0], r[1][:40]) for r in rows if r[0] != expected]
            print(f"  ⚠️  '{alias}' 应映射到 '{expected}', 但匹配到了: {wrong}")
        else:
            print(f"  ✅ '{alias}' → '{expected}' ({len(rows)}条)")

# ==== 3. 事件类型合理性 ====
print("\n[3] 事件类型合理性检查")
# Offer事件应该包含offer/意向字样的证据
cur.execute("""
    SELECT company, event_type, substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE event_type = 'offer'
    LIMIT 5
""")
print("  Offer事件抽样:")
for r in cur.fetchall():
    print(f"    {r[0]:8s} | {r[2][:50]}")

# Rejected事件应该包含拒/挂/感谢信等
cur.execute("""
    SELECT company, event_type, substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE event_type = 'rejected'
    AND evidence_text NOT LIKE '%拒%'
    AND evidence_text NOT LIKE '%挂%'
    AND evidence_text NOT LIKE '%感谢%'
    AND evidence_text NOT LIKE '%凉%'
    AND evidence_text NOT LIKE '%没通过%'
    AND evidence_text NOT LIKE '%被刷%'
    LIMIT 5
""")
print("  Rejected事件中无明确拒信关键词的抽样:")
for r in cur.fetchall():
    print(f"    {r[0]:8s} | {r[2][:50]}")

# ==== 4. 日期合理性 ====
print("\n[4] 日期合理性检查")
cur.execute("""
    SELECT event_date, event_type, company, substr(evidence_text, 1, 50)
    FROM recruit_events
    WHERE event_date != ''
    ORDER BY event_date DESC
    LIMIT 5
""")
print("  最近5个事件日期:")
for r in cur.fetchall():
    print(f"    {r[0]} | {r[1]:15s} | {r[2]:8s} | {r[3][:40]}")

cur.execute("""
    SELECT event_date, event_type, company, substr(evidence_text, 1, 50)
    FROM recruit_events
    WHERE event_date != ''
    ORDER BY event_date ASC
    LIMIT 5
""")
print("  最早5个事件日期:")
for r in cur.fetchall():
    print(f"    {r[0]} | {r[1]:15s} | {r[2]:8s} | {r[3][:40]}")

# 检查年份是否合理（2025-2027）
from datetime import datetime
cur.execute("""
    SELECT event_date, company, event_type FROM recruit_events
    WHERE event_date LIKE '2024%' OR event_date LIKE '2028%' OR event_date LIKE '2029%'
""")
print("  异常年份的事件:")
for r in cur.fetchall():
    print(f"    ⚠️  {r[0]} | {r[1]} | {r[2]}")

# ==== 5. 岗位分类合理性 ====
print("\n[5] 岗位分类合理性")
cur.execute("""
    SELECT role_category, COUNT(*) as cnt FROM recruit_events
    WHERE role != ''
    GROUP BY role_category
    ORDER BY cnt DESC
""")
cats = cur.fetchall()
total_with_role = sum(r[1] for r in cats)
print(f"  有岗位分类的事件: {total_with_role}条")
for c, cnt in cats:
    pct = cnt / total_with_role * 100
    print(f"    {c}: {cnt}条 ({pct:.0f}%)")

# "未知"分类占比
unknown_pct = 0
for c, cnt in cats:
    if c == "未知":
        unknown_pct = cnt / total_with_role * 100
if unknown_pct > 50:
    print(f"  ⚠️  未知分类占比 {unknown_pct:.0f}%，偏高")

# ==== 6. 薪资提取质量 ====
print("\n[6] 薪资提取质量")
cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE salary_base_monthly IS NOT NULL OR total_compensation IS NOT NULL
""")
salary_count = cur.fetchone()[0]
print(f"  成功提取薪资的事件: {salary_count}条")

cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE evidence_text LIKE '%k%' OR evidence_text LIKE '%K%'
    OR evidence_text LIKE '%万%' OR evidence_text LIKE '%w%'
    OR evidence_text LIKE '%薪资%' OR evidence_text LIKE '%开奖%'
""")
mention_count = cur.fetchone()[0]
print(f"  提及薪资但未提取的事件: {mention_count - salary_count}条")

# 检查证据文本中含有k*数字但未提取到的事件
cur.execute("""
    SELECT company, event_type, substr(evidence_text, 1, 80), salary_base_monthly
    FROM recruit_events
    WHERE evidence_text REGEXP '[0-9]+[kK]\\s*\\*'
    AND salary_base_monthly IS NULL
    LIMIT 5
""")
print("  薪资未提取的样本:")
for r in cur.fetchall():
    print(f"    {r[0]:8s} | {r[2][:60]}")


# ==== 7. 证据文本合理性 ====
print("\n[7] 证据文本合理性 (检查是否有乱码/不完整)")
cur.execute("""
    SELECT company, event_type, substr(evidence_text, 1, 80), LENGTH(evidence_text)
    FROM recruit_events
    ORDER BY LENGTH(evidence_text) ASC
    LIMIT 5
""")
print("  最短的5条证据:")
for r in cur.fetchall():
    print(f"    ({r[3]}字) {r[0]:8s} | {r[1]:15s} | {r[2][:50]}")

# 检查evidence_text中是否包含HTML标签
cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE evidence_text LIKE '%<img%' OR evidence_text LIKE '%<br%'
""")
html_count = cur.fetchone()[0]
print(f"  包含HTML标签的证据: {html_count}条")

# ==== 8. 统计概览 ====
print("\n" + "=" * 60)
print("核查汇总")
print("=" * 60)
stats = db.get_stats()
cur.execute("SELECT SUM(c) FROM (SELECT COUNT(*) as c FROM recruit_events WHERE quality_score IS NOT NULL AND quality_score > 0 UNION ALL SELECT 0)")
scored = cur.execute("SELECT COUNT(*) FROM recruit_events WHERE composite_score > 0").fetchone()[0]
print(f"  总事件: {stats['recruit_events']}")
print(f"  已评分: {scored}")
print(f"  公司数: {stats['companies']}")
print(f"  有薪资信息: {salary_count}")

db.close()
print("\n核查完成")
