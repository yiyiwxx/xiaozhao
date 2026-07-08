"""删除所有误匹配公司名的事件并重解析"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database

db = Database(CRAWL_CONFIG['db_path'])
cur = db.conn.cursor()

# 列出所有疑似误匹配的公司名
cur.execute("""
    SELECT company, COUNT(*) as cnt
    FROM recruit_events
    GROUP BY company
    ORDER BY cnt DESC
""")
all_companies = cur.fetchall()

# 已知有效的公司名
known_good = {
    "腾讯", "字节跳动", "阿里巴巴", "阿里云", "蚂蚁集团",
    "美团", "拼多多", "京东", "快手", "小红书", "哔哩哔哩",
    "百度", "华为", "小米", "OPPO", "vivo",
    "网易", "携程", "理想", "小鹏", "蔚来", "比亚迪",
    "海康威视", "科大讯飞", "中兴", "大疆",
    "深信服", "广联达", "超星",
    "TP-LINK", "地平线",
    "TCL", "元戎启行", "佑驾创新", "芯恩",
    "新凯来", "创维", "中广核",
    "荣耀", "美的",
    "恒生电子", "北方华创", "壁仞科技", "迪普科技",
    "汇川", "北部湾港集团",
    "卓驭", "速腾聚创", "中芯", "华虹", "武汉新芯",
    "Shopee", "佰钧成", "路特创新",
}

deleted_total = 0
for company, cnt in all_companies:
    if company not in known_good:
        cur.execute("DELETE FROM recruit_events WHERE company = ?", (company,))
        deleted = cur.rowcount
        if deleted > 0:
            print(f"删除 '{company}': {deleted}条")
            deleted_total += deleted

db.conn.commit()
print(f"\n共删除 {deleted_total} 条误匹配事件")
db.close()

# 重解析
from crawler.pipeline import Pipeline
p = Pipeline(CRAWL_CONFIG['db_path'])
p.run_parse()
p.close()
