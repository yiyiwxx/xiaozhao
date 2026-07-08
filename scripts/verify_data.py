"""
数据完整性验证
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.config import CRAWL_CONFIG
from crawler.database import Database
from crawler.aggregator import Aggregator

db = Database(CRAWL_CONFIG['db_path'])
agg = Aggregator(db)

stats = db.get_stats()
print(f"统计: {stats}")

companies = db.get_all_companies()
print(f"\n覆盖公司 ({len(companies)}家):")
for c in companies:
    events = db.get_events_by_company(c)
    types = set(e['event_type'] for e in events)
    print(f"  {c}: {len(events)}事件, 阶段:{types}")

print("\n=== 腾讯时间线样例 ===")
tl = agg.company_timeline('腾讯')
if tl.get('events'):
    for e in tl['events'][:5]:
        print(f"  {e['date']} | {e['event']} | 岗位:{e['role']} | 置信度:{e['confidence']} | 证据:{e['evidence'][:60]}")

print("\n=== 薪资事件 ===")
salary_events = db.get_events_by_type('salary')
for e in salary_events[:5]:
    print(f"  {e['company']} | 月薪:{e['salary_base_monthly']}k | *{e['salary_months']}月 | 总包:{e['total_compensation']}w | 证据:{e['evidence_text'][:80]}")

db.close()
