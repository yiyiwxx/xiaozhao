"""
每日增量抓取脚本

Windows 定时任务配置:
1. 打开"任务计划程序"
2. 创建基本任务
3. 触发器: 每天, 时间: 09:00
4. 操作: 启动程序
   - 程序: python
   - 参数: D:\校招系统\scripts\daily_crawl.py
   - 起始于: D:\校招系统

手动运行:
   python scripts/daily_crawl.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from crawler.pipeline import Pipeline


def daily_run():
    print(f"{'='*50}")
    print(f"每日增量抓取 - {datetime.now().isoformat()}")
    print(f"{'='*50}")

    pipeline = Pipeline()
    try:
        # 每天只抓取前2页的新内容（增量更新）
        stats = pipeline.run_full(max_pages=2)

        # 导出最新数据
        from crawler.aggregator import Aggregator
        agg = Aggregator(pipeline.db)
        export_path = "data/export.json"
        agg.export_json(export_path)
        print(f"数据已导出: {export_path}")

        print(f"\n✅ 每日抓取完成")
        return stats
    except Exception as e:
        print(f"\n❌ 抓取失败: {e}")
        raise
    finally:
        pipeline.close()


if __name__ == "__main__":
    daily_run()
