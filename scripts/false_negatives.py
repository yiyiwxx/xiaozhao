"""
深挖被丢弃的记录 — 哪些本来不应该丢
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.parsers import COMPANY_ALIAS
from crawler.database import Database
import re

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 获取所有未产生事件的记录
cur.execute("""
    SELECT r.content_id, r.title, r.content, r.topic_uuid
    FROM raw_records r
    WHERE NOT EXISTS (
        SELECT 1 FROM recruit_events e WHERE e.content_id = r.content_id
    )
    AND r.title != ''
    ORDER BY r.first_seen DESC
""")
discarded = cur.fetchall()
print(f"共 {len(discarded)} 条被丢弃的记录（有标题）\n")

# 分类分析
categories = {
    "公司名在已知别名中": [],
    "公司名在标题但不在别名": [],
    "公司名在正文(仅)": [],
    "无公司名的讨论/提问": [],
    "纯内推/广告帖": [],
    "其他": [],
}

# 常见未收录的公司名（手动维护，用于探测）
UNLISTED_COMPANIES = [
    "佑驾创新", "蔚来", "中兴", "深信服", "用友", "金蝶",
    "商汤", "旷视", "地平线", "Momenta", "元戎启行",
    "FunPlus", "莉莉丝", "叠纸", "鹰角",
    "宁德时代", "远景能源", "TCL", "海尔", "格力",
    "微众银行", "招银网络", "中信", "中金", "华泰",
    "携程", "去哪儿", "贝壳", "链家",
    "作业帮", "猿辅导", "跟谁学", "高途",
    "大疆", "DJI",
    "Thoughtworks", "中软国际", "神州信息",
    "广联达", "用友网络",
    "三星", "Intel", "微软", "Google", "Amazon",
    "SHEIN", "希音", "Temu",
]

for row in discarded:
    cid, title, content, tuuid = row
    full = f"{title} {content}"[:2000]

    # 检查是否在已知别名中（那为什么会没匹配到？）
    matched_aliases = []
    for alias, std in sorted(COMPANY_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in title or alias in (content or ""):
            matched_aliases.append((alias, std))

    if matched_aliases:
        categories["公司名在已知别名中"].append((title, matched_aliases, content[:200]))
        continue

    # 检查是否含未收录的公司
    for uc in UNLISTED_COMPANIES:
        if uc in full:
            categories["公司名在标题但不在别名"].append((title, uc, content[:200]))
            break
    else:
        # 是否含"公司"或"集团"关键词（通用模式本该匹配的）
        if re.search(r'[\u4e00-\u9fa5]{2,6}(?:公司|集团)', full):
            categories["公司名在正文(仅)"].append((title, content[:200]))
        # 是否含内推/招聘关键词
        elif re.search(r'(内推|校招|招聘|实习|面经|offer|投递|简历)', full, re.IGNORECASE):
            categories["纯内推/广告帖"].append((title, content[:200]))
        elif re.search(r'(请问|想问|怎么|如何|求问|有没有|求助)', full):
            categories["无公司名的讨论/提问"].append((title, content[:200]))
        else:
            categories["其他"].append((title, content[:200]))

# 输出分析
for cat_name, items in categories.items():
    print(f"{'='*60}")
    print(f"[{cat_name}] {len(items)} 条")
    print(f"{'='*60}")
    for i, item in enumerate(items[:8]):  # 每个分类最多看8条
        if cat_name == "公司名在已知别名中":
            title, aliases, content = item
            alias_str = ", ".join(f"{a}→{s}" for a, s in aliases)
            print(f"  ⚠️  '{title[:60]}'")
            print(f"     命中别名: {alias_str}")
            print(f"     内容: {content[:80]}")
        elif cat_name == "公司名在标题但不在别名":
            title, company, content = item
            print(f"  🔸  '{title[:60]}'")
            print(f"     未收录公司: {company}")
            print(f"     内容: {content[:80]}")
        else:
            title, content = item
            print(f"  •  '{title[:60]}'")
            print(f"     {content[:80]}")
        print()

# 重点: 已知别名中哪些被漏掉了
print(f"\n{'='*60}")
print("重点分析: 已有别名但没匹配上的帖子")
print(f"{'='*60}")
known_alias_miss = categories["公司名在已知别名中"]
if known_alias_miss:
    # 看看是什么原因导致 alias 匹配失败
    for title, aliases, content in known_alias_miss[:10]:
        print(f"\n标题: {title[:80]}")
        for alias, std in aliases:
            # 检查 title 中 alias 的位置
            t_pos = (title or "").find(alias)
            c_pos = (content or "").find(alias)
            print(f"  别名 '{alias}'→'{std}' 在标题位置:{t_pos} 内容位置:{c_pos}")
        # 再看看 normalized_company 会返回什么
        from crawler.parsers import normalize_company
        actual_company, bg = normalize_company(f"{title} {content}"[:2000])
        print(f"  normalize_company 实际返回: '{actual_company}' bg='{bg}'")

db.close()
