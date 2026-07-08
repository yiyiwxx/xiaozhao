"""
管道协调器: 抓取 -> 解析 -> 存储
"""

import os
import sys
import time
from datetime import datetime

from crawler.config import CRAWL_CONFIG, TOPICS
from crawler.database import Database
from crawler.fetcher import Fetcher
from crawler.parsers import extract_events
from crawler.scorer import score_events


class Pipeline:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = CRAWL_CONFIG["db_path"]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = Database(db_path)

    def run_fetch(self, max_pages: int = 3, since_timestamp: int = None):
        """阶段二: 抓取原始数据"""
        fetcher = Fetcher(self.db)
        return fetcher.crawl_all(max_pages=max_pages, since_timestamp=since_timestamp)

    def run_parse(self, limit: int = None):
        """阶段三: 解析原始记录为结构化事件"""
        import sqlite3
        cur = self.db.conn.cursor()

        # 获取未解析/更新的原始记录
        cur.execute("""
            SELECT r.* FROM raw_records r
            WHERE NOT EXISTS (
                SELECT 1 FROM recruit_events e
                WHERE e.content_id = r.content_id
            )
            ORDER BY r.first_seen DESC
        """)
        if limit:
            rows = cur.fetchmany(limit)
        else:
            rows = cur.fetchall()

        total = len(rows)
        new_events = 0
        updated = 0
        skipped_old = 0
        min_publish = CRAWL_CONFIG.get("min_publish_ms", 0)

        print(f"开始解析 {total} 条原始记录...")

        for i, row in enumerate(rows):
            if i % 50 == 0 and i > 0:
                print(f"  进度: {i}/{total}, 已提取 {new_events} 个事件")

            # 时间过滤: 跳过旧数据（如果配置了）
            publish_ms = row["show_time"] or row["create_time"] or 0
            if min_publish > 0 and publish_ms > 0 and publish_ms < min_publish:
                skipped_old += 1
                continue

            try:
                import json
                raw = json.loads(row["raw_json"])

                # 从原始数据中提取 detail_url
                md = raw.get("momentData") or {}
                cd = raw.get("contentData") or {}
                if md and md.get("uuid"):
                    detail_url = f"https://www.nowcoder.com/feed/main/detail/{md['uuid']}"
                elif cd and cd.get("id"):
                    detail_url = f"https://www.nowcoder.com/discuss/{cd['id']}"
                else:
                    detail_url = ""

                # 获取作者信息
                ub = raw.get("userBrief") or {}
                author_id = str(raw.get("creator", "") or ub.get("userId", ""))
                edu_info = ub.get("educationInfo", "") or ""
                auth_display = ub.get("authDisplayInfo", "") or ""

                events = extract_events(
                    title=row["title"] or "",
                    content=row["content"] or "",
                    topic_uuid=row["topic_uuid"],
                    content_id=row["content_id"],
                    publish_time_ms=row["show_time"] or row["create_time"],
                    education_info=edu_info,
                    auth_display=auth_display,
                    detail_url=detail_url,
                    author_id=author_id,
                )

                # 三层评分
                if events:
                    events = score_events(row["title"] or "", row["content"] or "", events)

                for event in events:
                    is_new = self.db.save_event(event)
                    if is_new:
                        new_events += 1
                    else:
                        updated += 1

            except Exception as e:
                print(f"  解析失败 {row['content_id']}: {e}")
                continue

        print(f"解析完成! 新增 {new_events}, 更新 {updated} 个事件")
        return {"parsed": total, "new_events": new_events, "updated": updated}

    def run_full(self, max_pages: int = 3):
        """完整管道: 抓取 + 解析"""
        start = time.time()

        print(f"=== 校招进度聚合器 - 完整运行 ===")
        print(f"时间: {datetime.now().isoformat()}\n")

        # 1. 抓取
        print("[阶段一] 增量抓取")
        fetch_stats = self.run_fetch(max_pages=max_pages)
        print(f"  抓取结果: {fetch_stats}\n")

        # 2. 解析
        print("[阶段二] 事件提取")
        parse_stats = self.run_parse()
        print(f"  提取结果: {parse_stats}\n")

        # 3. 统计
        stats = self.db.get_stats()
        print(f"[统计]")
        print(f"  原始记录: {stats['raw_records']}")
        print(f"  招聘事件: {stats['recruit_events']}")
        print(f"  涉及公司: {stats['companies']}")
        print(f"  事件类型分布: {stats['event_type_distribution']}")

        elapsed = time.time() - start
        print(f"\n总耗时: {elapsed:.1f}s")

        return stats

    def close(self):
        self.db.close()


def main():
    pipeline = Pipeline()
    try:
        pipeline.run_full(max_pages=3)
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
