"""
生成脱敏样例数据 - 从数据库导出为可读JSON
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.config import CRAWL_CONFIG
from crawler.database import Database
from crawler.aggregator import Aggregator


def export_sample(output_path: str = "data/sample_data.json"):
    db = Database(CRAWL_CONFIG["db_path"])
    agg = Aggregator(db)

    stats = db.get_stats()
    companies = db.get_all_companies()

    # 取前10家公司的详细时间线
    timelines = []
    for c in companies[:10]:
        tl = agg.company_timeline(c)
        if tl.get("events"):
            timelines.append(tl)

    # 低置信度事件
    low_conf = agg.low_confidence_events(threshold=0.6)

    # 产品岗位事件
    product_events = agg.filter_by_role("产品")

    sample = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "数据说明": "脱敏样例数据，不包含个人身份信息。作者ID已哈希处理。",
        "合规声明": "仅使用牛客网公开话题API，低频请求，遇验证码即停。",
        "数据来源": "https://gw-c.nowcoder.com/api/sparta/subject/newest-content",
        "统计": {
            "原始记录数": stats["raw_records"],
            "招聘事件数": stats["recruit_events"],
            "覆盖公司数": stats["companies"],
            "事件类型分布": stats["event_type_distribution"],
        },
        "公司时间线样例": [
            {
                "公司": tl["company"],
                "事件数": tl["event_count"],
                "阶段概览": tl["stage_summary"],
                "最新更新时间": tl["latest_update"],
                "薪资样本": tl.get("salary_summary"),
                "事件列表": [
                    {
                        "日期": e["date"],
                        "事件": e["event"],
                        "岗位": e["role"],
                        "岗位分类": e["role_category"],
                        "置信度": e["confidence"],
                        "证据": e["evidence"][:100],
                        "地点": e.get("location", ""),
                    }
                    for e in tl["events"][:5]  # 每个公司只取5条
                ]
            }
            for tl in timelines
        ],
        "产品岗位事件样例": [
            {
                "公司": e.get("company", ""),
                "日期": e.get("event_date", ""),
                "事件类型": e.get("event_type", ""),
                "置信度": e.get("confidence", 0),
                "证据": e.get("evidence_text", "")[:100],
            }
            for e in product_events[:10]
        ],
        "待复核低置信度事件数": len(low_conf),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    print(f"样例数据已导出: {output_path}")
    print(f"  统计: {stats}")
    print(f"  公司时间线: {len(timelines)} 家")
    print(f"  产品岗位事件: {len(product_events)} 条")
    print(f"  低置信度事件: {len(low_conf)} 条")

    db.close()
    return sample


if __name__ == "__main__":
    export_sample()
