"""
最后一轮遗漏排查 — 还有什么没补上
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.parsers import COMPANY_ALIAS
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

print("=" * 65)
print(f"最终遗漏排查 — 别名已补全 ({len(COMPANY_ALIAS)} 个别名)")
print("=" * 65)

# === 1. 还是被丢弃的记录 ===
cur.execute("""
    SELECT r.content_id, r.title, substr(r.content, 1, 150)
    FROM raw_records r
    WHERE NOT EXISTS (
        SELECT 1 FROM recruit_events e WHERE e.content_id = r.content_id
    )
    AND r.title != ''
    ORDER BY r.first_seen DESC
""")
still_discarded = cur.fetchall()
print(f"\n[检查1] 仍被丢弃的记录: {len(still_discarded)} 条")

# 分类仍有公司名的
has_company_but_no_event = 0
new_company_candidates = set()
for row in still_discarded[:50]:
    cid, title, content = row
    full = f"{title} {content}"[:2000]
    found = False
    for alias, std in sorted(COMPANY_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in full:
            found = True
            break
    if found:
        has_company_but_no_event += 1
        if row[0] == still_discarded[0][0]:
            print(f"  ⚠️ 有别名但仍无事件的: '{title[:60]}'")
    else:
        # 看看是否有新公司名
        for m in re.finditer(r'([\u4e00-\u9fa5]{2,6})(?:公司|集团)', full):
            name = m.group(1)
            if name not in new_company_candidates:
                new_company_candidates.add(name)

print(f"  其中含别名的: {has_company_but_no_event} 条（正常过滤，无招聘阶段关键词）")
if new_company_candidates:
    print(f"  未收录的公司名候选项: {sorted(new_company_candidates)[:10]}")

# === 2. "多多" 别名是否有误匹配 ===
print(f"\n[检查2] '多多' 别名质量")
cur.execute("""
    SELECT company, substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE company = '拼多多'
    AND evidence_text LIKE '%多多%'
    AND evidence_text NOT LIKE '%拼多多%'
    ORDER BY random()
    LIMIT 5
""")
pdd_doduo = cur.fetchall()
if pdd_doduo:
    print("  '多多' 匹配到的帖子中不含'拼多多'字样:")
    for r in pdd_doduo:
        print(f"    {r[1][:60]}")
else:
    print("  ✅ '多多' 匹配全部伴有 '拼多多' 或 'pdd'，无歧义")

# === 3. 新公司的数据质量 ===
print(f"\n[检查3] 新收录公司的数据")
for new_co in ["TCL", "新凯来", "芯恩", "元戎启行", "佑驾创新"]:
    cur.execute("""
        SELECT substr(evidence_text, 1, 80)
        FROM recruit_events WHERE company = ?
        LIMIT 2
    """, (new_co,))
    rows = cur.fetchall()
    if rows:
        print(f"  ✅ {new_co}: {len(rows)} 条事件")
        for r in rows:
            print(f"     {r[0][:60]}")
    else:
        print(f"  ⚪ {new_co}: 0 条（别名已加但数据集中暂无此公司帖子）")

# === 4. 单个 content_id 是否有多事件但被截断 ===
print(f"\n[检查4] 去重是否丢失了事件")
# 检查同一个 content_id 下有多个不同 event_date 但同 event_type 被合并
cur.execute("""
    SELECT content_id, event_type, COUNT(*) as cnt
    FROM recruit_events
    GROUP BY content_id, event_type
    HAVING cnt > 1
    LIMIT 5
""")
dup = cur.fetchall()
if dup:
    print(f"  发现 {len(dup)} 个 content_id+event_type 组有重复事件:")
    for r in dup:
        print(f"    {r[0]}: {r[1]} ×{r[2]}")
        # 看具体是什么
        cur.execute("""
            SELECT event_date, substr(evidence_text, 1, 50)
            FROM recruit_events
            WHERE content_id = ? AND event_type = ?
        """, (r[0], r[1]))
        for dr in cur.fetchall():
            print(f"      date={dr[0]}, {dr[1][:50]}")
else:
    print("  ✅ 无重复事件（唯一约束正常发挥作用）")

# 但是否有 content_id 只产生1个事件但实际包含多个阶段？
cur.execute("""
    SELECT content_id, COUNT(*) as cnt
    FROM recruit_events
    GROUP BY content_id
    ORDER BY cnt ASC
    LIMIT 5
""")
single_events = cur.fetchall()
cur.execute("""
    SELECT content_id, COUNT(*) as cnt
    FROM recruit_events
    GROUP BY content_id
    ORDER BY cnt DESC
    LIMIT 5
""")
multi_events = cur.fetchall()
print(f"  单事件content_id数: 查看前5项")
for r in single_events:
    # 取对应原始记录标题
    cur.execute("SELECT title FROM raw_records WHERE content_id = ?", (r[0],))
    t = cur.fetchone()
    print(f"    {r[0][:20]}: {r[1]}个事件, T:{t[0][:50] if t else '?'}")

# === 5. 薪资提取看还有多少能捞 ===
print(f"\n[检查5] 薪资遗漏分析")
# 有k*数字但未提取
cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE evidence_text LIKE '%k*%' AND salary_base_monthly IS NULL
""")
missing_k = cur.fetchone()[0]
print(f"  证据含 'k*' 但未提取: {missing_k} 条")


# 无k后缀但含*数字的表达
cur.execute("""
    SELECT substr(evidence_text, 1, 60)
    FROM recruit_events
    WHERE evidence_text LIKE '%*%'
    AND salary_base_monthly IS NULL
    AND evidence_text NOT LIKE '%k*%'
    AND evidence_text NOT LIKE '%开奖%'
    AND evidence_text NOT LIKE '%总包%'
    AND evidence_text NOT LIKE '%实习%'
    LIMIT 5
""")
other_salary = cur.fetchall()
if other_salary:
    print("  其他含*的数字表达（可能薪资）:")
    for r in other_salary:
        print(f"    {r[0][:50]}")
else:
    print("  无其他含*的数字表达")

# 查看"开奖"事件中有多少带具体数值
cur.execute("""
    SELECT COUNT(*) FROM recruit_events
    WHERE event_type = 'salary'
    AND (salary_base_monthly IS NOT NULL OR total_compensation IS NOT NULL)
""")
salary_with_value = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM recruit_events WHERE event_type = 'salary'")
salary_total = cur.fetchone()[0]
print(f"  开奖事件: {salary_total} 条, 有具体数值: {salary_with_value} 条 ({salary_with_value/salary_total*100:.0f}%)")

# === 6. 事件类型是否有常见的缺失 ===
print(f"\n[检查6] 事件类型完整度")
all_types = {"application","resume_screening","written_test","first_interview",
             "second_interview","third_interview","hr_interview","pool",
             "rejected","revived","oc","offer","salary"}
cur.execute("SELECT DISTINCT event_type FROM recruit_events")
existing_types = {r[0] for r in cur.fetchall()}
missing_types = all_types - existing_types
if missing_types:
    print(f"  缺失类型: {missing_types}")
else:
    print(f"  ✅ 全部 13 种事件类型已覆盖")

# 看看简历筛选(resume_screening)是否很少
for t in existing_types:
    cur.execute("SELECT COUNT(*) FROM recruit_events WHERE event_type = ?", (t,))
    cnt = cur.fetchone()[0]
    print(f"    {t}: {cnt}")

db.close()
print("\n排查完成")
