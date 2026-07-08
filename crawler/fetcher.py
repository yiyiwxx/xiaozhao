"""
阶段二：增量抓取器
- 低频、可恢复的增量抓取
- 支持配置多个话题 UUID
- 自动遍历分页，设置最大页数
- 请求间隔不少于 2 秒，加入随机延迟
- 对 403/429/5xx 使用有限次数指数退避
- 检测验证码或 WAF 后停止该来源
- 使用 content_id 去重
"""

import json
import os
import random
import time
import requests
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from crawler.config import (
    TOPICS, CRAWL_CONFIG, API_BASE, HEADERS
)
from crawler.database import Database


class Fetcher:
    def __init__(self, db: Database):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.stats = {"new_records": 0, "updated": 0, "errors": 0}

    def _check_waf(self, resp: requests.Response) -> bool:
        """检查响应是否为 WAF/验证码页面"""
        ct = resp.headers.get("Content-Type", "")
        if "text/html" in ct:
            body = resp.text[:1000].lower()
            if any(kw in body for kw in [
                "验证", "captcha", "waf", "access denied",
                "请滑动", "slid", "verify", "安全验证",
                "请完成验证",
            ]):
                return True
        return False

    def _fetch_page(self, topic_uuid: str, page_no: int) -> Optional[dict]:
        """抓取单页数据，带退避重试"""
        url = f"{API_BASE}?{urlencode({'pageNo': page_no, 'uuid': topic_uuid})}"

        for attempt in range(CRAWL_CONFIG["max_retries"] + 1):
            try:
                resp = self.session.get(
                    url, timeout=CRAWL_CONFIG["request_timeout"]
                )

                # WAF 检测
                if self._check_waf(resp):
                    return {"_waf": True, "error": "WAF/验证码拦截"}

                if resp.status_code == 429:
                    wait = CRAWL_CONFIG["backoff_base"] ** (attempt + 1) * 3
                    print(f"      429限流，等待{wait}s后重试...")
                    time.sleep(wait)
                    continue

                if resp.status_code >= 500:
                    wait = CRAWL_CONFIG["backoff_base"] ** (attempt + 1)
                    print(f"      服务器错误{resp.status_code}，等待{wait}s后重试...")
                    time.sleep(wait)
                    continue

                if resp.status_code != 200:
                    print(f"      非预期状态码: {resp.status_code}")
                    return None

                data = resp.json()
                return data

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < CRAWL_CONFIG["max_retries"]:
                    wait = CRAWL_CONFIG["backoff_base"] ** (attempt + 1)
                    print(f"      请求异常({e})，等待{wait}s后重试...")
                    time.sleep(wait)
                else:
                    print(f"      请求失败: {e}")
                    return None

        return None

    def _parse_record(self, record: dict, topic_uuid: str, topic_name: str) -> Optional[dict]:
        """解析单条记录，返回标准化字典"""
        md = record.get("momentData") or {}
        cd = record.get("contentData") or {}
        ub = record.get("userBrief") or {}

        content_id = record.get("contentId", "")
        content_type = record.get("contentType", "")

        if not content_id:
            content_id = md.get("uuid", "") or str(cd.get("id", ""))

        title = md.get("title", "") or cd.get("title", "")
        content_text = md.get("content", "") or cd.get("content", "")

        # 时间戳(毫秒)
        show_time = md.get("showTime") or cd.get("showTime") or 0
        create_time = cd.get("createTime") or 0

        # 公司名
        internal_recommend = record.get("internalRecommend") or {}
        company_name = internal_recommend.get("companyName", "")

        # 作者教育信息
        edu_info = ub.get("educationInfo", "") or ""
        auth_display = ub.get("authDisplayInfo", "") or ""

        # 详情URL
        if md and md.get("uuid"):
            detail_url = f"https://www.nowcoder.com/feed/main/detail/{md['uuid']}"
        elif cd and cd.get("id"):
            detail_url = f"https://www.nowcoder.com/discuss/{cd['id']}"
        else:
            detail_url = ""

        result = {
            "content_id": str(content_id),
            "topic_uuid": topic_uuid,
            "content_type": content_type,
            "title": title,
            "content": content_text[:3000],  # 截断长内容
            "show_time": show_time,
            "create_time": create_time,
            "company_name": company_name,
            "detail_url": detail_url,
            "education_info": edu_info,
            "auth_display": auth_display,
            "raw_record": record,
        }
        return result

    def crawl_topic(self, topic_name: str, topic_uuid: str,
                    max_pages: int = None, since_time: Optional[int] = None):
        """抓取单个话题"""
        if max_pages is None:
            max_pages = CRAWL_CONFIG["max_pages"]

        print(f"\n  ▶ 抓取话题: {topic_name}")

        # 获取上次进度
        progress = self.db.get_crawl_progress(topic_uuid)
        start_page = 1
        if progress and progress.get("last_page"):
            start_page = progress["last_page"]
            print(f"    从第{start_page}页继续")

        for page in range(start_page, start_page + max_pages):
            print(f"    第{page}页...", end=" ")
            data = self._fetch_page(topic_uuid, page)

            if data is None:
                self.stats["errors"] += 1
                self.db.update_crawl_progress(
                    topic_uuid, topic_name, page, 0,
                    error_info=f"第{page}页抓取失败"
                )
                break

            if data.get("_waf"):
                print(f"❌ {data['error']}")
                self.db.update_crawl_progress(
                    topic_uuid, topic_name, page, 0,
                    error_info=data["error"]
                )
                break

            # 解析
            records = []
            d = data.get("data", {})
            if isinstance(d, dict):
                records = d.get("records", [])
                total = d.get("total", 0)
                total_page = d.get("totalPage", 0)

            if not records:
                print("无更多记录")
                # 更新进度
                self.db.update_crawl_progress(
                    topic_uuid, topic_name, page, 0
                )
                break

            page_new = 0
            page_upd = 0
            for record in records:
                parsed = self._parse_record(record, topic_uuid, topic_name)
                if not parsed:
                    continue

                # 时间过滤
                if since_time and parsed["show_time"] and parsed["show_time"] < since_time:
                    continue

                # 保存原始记录
                is_new = self.db.save_raw_record(
                    content_id=parsed["content_id"],
                    topic_uuid=topic_uuid,
                    content_type=parsed["content_type"],
                    raw_json=record,
                    title=parsed["title"],
                    content=parsed["content"],
                    show_time=parsed["show_time"],
                    create_time=parsed["create_time"],
                    company_name=parsed["company_name"],
                    detail_url=parsed.get("detail_url", ""),
                )

                if is_new:
                    page_new += 1
                else:
                    page_upd += 1

            self.stats["new_records"] += page_new
            self.stats["updated"] += page_upd

            # 更新进度
            self.db.update_crawl_progress(
                topic_uuid, topic_name, page,
                total if page == 1 else 0
            )

            print(f"✅ 新增{page_new}, 更新{page_upd}")

            # 最后一页判断
            if page >= total_page and total_page > 0:
                print(f"    已到达最后一页（共{total_page}页）")
                break

            # 请求间隔
            delay = CRAWL_CONFIG["min_interval"] + random.uniform(0, 1.5)
            time.sleep(delay)

        print(f"    ✓ 完成")

    def crawl_all(self, max_pages: int = None, since_timestamp: Optional[int] = None):
        """抓取所有配置的话题"""
        self.stats = {"new_records": 0, "updated": 0, "errors": 0}
        start_time = time.time()

        print(f"开始增量抓取 - {datetime.now().isoformat()}")
        print(f"共{len(TOPICS)}个话题, 每话题最多{max_pages or CRAWL_CONFIG['max_pages']}页")

        for name, uuid in TOPICS.items():
            self.crawl_topic(name, uuid, max_pages, since_timestamp)

        elapsed = time.time() - start_time
        print(f"\n{'='*50}")
        print(f"抓取完成! 耗时{elapsed:.1f}s")
        print(f"  新增记录: {self.stats['new_records']}")
        print(f"  更新记录: {self.stats['updated']}")
        print(f"  错误次数: {self.stats['errors']}")

        return self.stats


def main():
    db_path = CRAWL_CONFIG["db_path"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = Database(db_path)
    fetcher = Fetcher(db)

    try:
        fetcher.crawl_all(max_pages=3)
    finally:
        db.close()


if __name__ == "__main__":
    main()
