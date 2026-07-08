"""
扫描被丢弃记录中潜在的公司名
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 取被丢弃记录（有标题的）
cur.execute("""
    SELECT r.title, substr(r.content, 1, 300)
    FROM raw_records r
    WHERE NOT EXISTS (
        SELECT 1 FROM recruit_events e WHERE e.content_id = r.content_id
    )
    AND r.title != ''
""")
discarded = cur.fetchall()
print(f"被丢弃记录总数: {len(discarded)}\n")

# 常用公司名后缀/上下文模式
company_patterns = [
    # "xxx公司" 模式
    (r'([\u4e00-\u9fa5]{2,8})(?:公司|集团)', '公司/集团后缀'),
    # 标题中常见的 "xxx | 2026校招" "xxx2026校招" 模式
    (r'^([\u4e00-\u9fa5A-Za-z]{2,12})[|｜\s]*(?:20\d{2}|校招|春招|秋招|内推|实习)', '标题校招前缀'),
    # "xxx校招" "xxx内推" 模式
    (r'^([\u4e00-\u9fa5A-Za-z]{2,12})(?:20\d{2}届|校招|春招|秋招|内推|实习|面经)', '标题招聘后缀'),
    # "xxx，xxx" 对比模式
    (r'^([\u4e00-\u9fa5]{2,8})[VSvs]', '对比标题'),
]

found_candidates = set()
for title, content in discarded:
    full = f"{title} {content}"[:1000]
    for pattern, label in company_patterns:
        for m in re.finditer(pattern, full):
            name = m.group(1)
            # 简单过滤: 纯公司名长度大于1
            if len(name) >= 2:
                found_candidates.add((name, label, title[:60]))

# 统计频次
from collections import Counter
name_counter = Counter()
name_examples = {}
for name, label, example in found_candidates:
    name_counter[name] += 1
    if name not in name_examples:
        name_examples[name] = (label, example)

# 输出高频候选项（出现2次以上且不在已知别名表中）
from crawler.parsers import COMPANY_ALIAS
known = set(COMPANY_ALIAS.values()) | set(COMPANY_ALIAS.keys())

print(f"发现 {len(name_counter)} 个候选公司名（含重复）\n")
print(f"{'候选名':16s} {'次数':>4s} {'来源模式':12s} {'示例':>40s}")
print("-" * 75)

new_candidates = []
for name, cnt in name_counter.most_common(60):
    if name not in known and len(name) >= 2:
        label, example = name_examples.get(name, ("", ""))
        # 过滤明显不是公司名的
        if any(kw in name for kw in ["的", "了", "是", "在", "有", "和", "与",
                                       "我", "你", "他", "这", "那", "什么",
                                       "请问", "怎么", "如何", "为什么", "已经",
                                       "没有", "不是", "还是", "因为", "所以",
                                       "打算", "考虑", "准备", "有人", "所有",
                                       "包括", "比如", "作为", "目前", "现在",
                                       "最近", "刚刚", "之后", "之前", "以上"]):
            continue
        new_candidates.append((name, cnt, label, example))
        print(f"{name:16s} {cnt:>4d}次 {label:12s} {example[:40]}")

print(f"\n{'=' * 75}")
print(f"未收录的高频公司名候选: {len(new_candidates)} 个")

# 特别检查一些已知但可能不在别名中的
common_missed = [
    "卓驭", "速腾聚创", "佰钧成", "新竹", "善仁新材",
    "中芯", "华虹", "武汉新芯", "路特创新",
    "虾皮", "Shopee",
]
print(f"\n特别检查（常见但可能漏掉的公司）:")
for name in common_missed:
    if name in known:
        print(f"  ✅ {name} 已在别名表中")
    else:
        cnt = name_counter.get(name, 0)
        print(f"  ⚠️ {name} 不在别名表中 (出现在 {cnt} 条记录中)")

# 检查被误删的真实公司
print(f"\n当前 whitelist 外的公司:")
cur.execute("SELECT company, COUNT(*) FROM recruit_events GROUP BY company ORDER BY company")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

db.close()
