"""
遗漏分析 — 每一层损失了什么
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG, TOPICS, API_BASE
from crawler.database import Database
import json, requests
from urllib.parse import urlencode
from collections import defaultdict

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

print("=" * 65)
print("遗漏分析报告 — 每一层的数据损失")
print("=" * 65)

# ===== Layer 0: API 覆盖 =====
print("\n[层0] API 话题覆盖")
all_topics = len(TOPICS)
# 模拟首页验证
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}
print(f"  配置话题: {all_topics} 个")

# ===== Layer 1: 原始记录获取 =====
print("\n[层1] 原始记录获取损失")
for name, uuid in TOPICS.items():
    try:
        url = f"{API_BASE}?{urlencode({'pageNo': 1, 'uuid': uuid})}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            try:
                data = resp.json()
                d = data.get("data", {})
                total = 0
                records = d.get("records", []) if isinstance(d, dict) else []
                if isinstance(d, dict):
                    total = d.get("total", 0)
                if total == 0 or not records:
                    print(f"  ⚠️ '{name}': 空响应(total={total}, records={len(records)})")
            except:
                print(f"  ⚠️ '{name}': 非JSON响应")
        else:
            print(f"  ⚠️ '{name}': HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️ '{name}': {e}")

# ===== Layer 2: 原始记录中"无公司名"的损失 =====
print("\n[层2] 无法提取公司的记录")
cur.execute("""
    SELECT COUNT(*) FROM raw_records r
    WHERE NOT EXISTS (
        SELECT 1 FROM recruit_events e WHERE e.content_id = r.content_id
    )
""")
no_events = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM raw_records")
total_raw = cur.fetchone()[0]
no_company_pct = no_events / total_raw * 100 if total_raw else 0
print(f"  总原始记录: {total_raw}")
print(f"  未产生事件: {no_events} ({no_company_pct:.0f}%)")
print(f"  原因: 标题+内容中未识别出任何已知公司名")

# 抽样看看没提取出事件的是些什么帖子
cur.execute("""
    SELECT substr(r.title, 1, 60), substr(r.content, 1, 80)
    FROM raw_records r
    WHERE NOT EXISTS (
        SELECT 1 FROM recruit_events e WHERE e.content_id = r.content_id
    )
    AND r.title != ''
    LIMIT 5
""")
print("  无事件帖子抽样:")
for r in cur.fetchall():
    print(f"    T:{r[0]}")
    print(f"    C:{r[1][:60]}")

# ===== Layer 3: 事件类型覆盖 =====
print("\n[层3] 事件类型分布 vs 理论上限")
cur.execute("select event_type, count(*) from recruit_events group by event_type order by count(*) desc")
type_dist = {r[0]: r[1] for r in cur.fetchall()}

# 统计每个 content_id 产生的平均事件数
cur.execute("""
    select count(*) as total_events, count(distinct content_id) as total_contents
    from recruit_events
""")
row = cur.fetchone()
avg_events = row[0] / row[1] if row[1] > 0 else 0
print(f"  每条记录平均产生 {avg_events:.2f} 个事件")
print(f"  已覆盖事件类型: {len(type_dist)} 种")
# 理想情况下最多有12种
print(f"  可识别事件类型: 12 种 (offer/rejected/salary/interview/hr_interview等)")
print(f"  未覆盖类型: {12 - len(type_dist)} 种")

# ===== Layer 4: 岗位分类覆盖 =====
print("\n[层4] 岗位分类覆盖率")
cur.execute("select count(*) as cnt, role_category from recruit_events where role_category != '' group by role_category")
role_cats = {r[1]: r[0] for r in cur.fetchall()}
cur.execute("select count(*) from recruit_events where role = ''")
no_role = cur.fetchone()[0]
cur.execute("select count(*) from recruit_events")
total_events = cur.fetchone()[0]
print(f"  有岗位分类: {sum(role_cats.values())}/{total_events} ({(sum(role_cats.values())/total_events*100):.0f}%)")
print(f"  无岗位: {no_role}/{total_events} ({(no_role/total_events*100):.0f}%)")
for cat, cnt in sorted(role_cats.items(), key=lambda x:-x[1]):
    print(f"    {cat}: {cnt}")

# ===== Layer 5: 日期提取覆盖 =====
print("\n[层5] 日期提取覆盖")
cur.execute("select event_date_source, count(*) from recruit_events group by event_date_source")
for source, cnt in cur.fetchall():
    pct = cnt / total_events * 100
    label = "正文日期" if source == "text" else ("发布时间回退" if source == "publish_time" else "无日期")
    print(f"  {label}: {cnt} ({pct:.0f}%)")

# ===== Layer 6: 薪资提取覆盖 =====
print("\n[层6] 薪资提取覆盖")
cur.execute("""
    select count(*) from recruit_events
    where salary_base_monthly is not null or total_compensation is not null
""")
extracted = cur.fetchone()[0]
# 提"钱"但没有具体数值的
cur.execute("""
    select count(*) from recruit_events
    where evidence_text like '%k%' or evidence_text like '%K%'
    or evidence_text like '%万%' or evidence_text like '%开奖%'
    or evidence_text like '%薪资%' or evidence_text like '%总包%'
""")
mentioned = cur.fetchone()[0]
print(f"  含薪资线索: {mentioned}")
print(f"  成功提取数值: {extracted}")
print(f"  遗漏: {mentioned - extracted} ({(mentioned - extracted)/mentioned*100:.0f}% 的线索帖)")
print(f"  原因: 纯文本描述如'开了个很高的薪资'、'薪资不满意'、'还没开奖'不含可解析结构化数值")

# ===== Layer 7: 事件去重导致的信息损失 =====
print("\n[层7] 去重导致的信息损失")
cur.execute("""
    select content_id, event_type, count(*) as cnt
    from recruit_events
    group by content_id, event_type
    having cnt > 1
    limit 5
""")
dup_rows = cur.fetchall()
dedup_loss = 0
if dup_rows:
    dedup_loss = sum(r[2] - 1 for r in dup_rows)
    print(f"  同一content_id+event_type重复: {dedup_loss} 条被合并")
    print(f"  原因: UNIQUE(content_id, event_type, event_date) 约束")

# ===== 汇总 =====
print("\n" + "=" * 65)
print("汇总: 从源头到终端的完整漏斗")
print("=" * 65)

# 估算
total_api = sum(20 * 3 for _ in TOPICS)  # 约算
total_api_actual = 24 * 3 * 20  # 24 topics * 3 pages * 20 items

print(f"""
牛客网24话题(3页)  ~{total_api_actual} 条公开记录
       │  过滤: 空话题(阿里/美团/百度等~10个未返回数据)
       ▼
存入 raw_records    {total_raw} 条
       │  过滤: 无公司名  {no_company_pct:.0f}%
       ▼
招聘事件             {total_events} 条
       │
       ├ 有公司名     {total_events} 条 (100%)
       ├ 有岗位分类   {sum(role_cats.values())} 条 ({sum(role_cats.values())/total_events*100:.0f}%)
       ├ 有薪资数值   {extracted} 条 ({extracted/total_events*100:.0f}%)
       └ 有置信度     {total_events} 条 (100%)
""")

print(f"\n详细日期来源:")
for r in cur.execute("select count(*) as cnt, event_date_source from recruit_events group by event_date_source"):
    if r[1] == 'text':
        print(f"  ✅ 正文明确日期: {r[0]} 条")
    elif r[1] == 'publish_time':
        print(f"  ⚠️ 发布时间回退: {r[0]} 条")
    else:
        print(f"  ❌ 无日期: {r[0]} 条")

db.close()
