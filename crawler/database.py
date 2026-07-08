"""
SQLite 数据库 - 存储原始响应和解析后的事件
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """初始化表结构"""
        cur = self.conn.cursor()

        # 原始抓取记录
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_records (
                content_id TEXT PRIMARY KEY,
                topic_uuid TEXT NOT NULL,
                content_type TEXT,
                raw_json TEXT NOT NULL,
                title TEXT,
                content TEXT,
                show_time INTEGER,
                create_time INTEGER,
                company_name TEXT,
                first_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)

        # 结构化招聘事件
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recruit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                topic_uuid TEXT NOT NULL,
                company TEXT NOT NULL,
                business_group TEXT DEFAULT '',
                role TEXT DEFAULT '',
                role_category TEXT DEFAULT '',
                location TEXT DEFAULT '',
                cohort TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                event_date TEXT DEFAULT '',
                event_date_source TEXT DEFAULT '',
                source_publish_time TEXT DEFAULT '',
                school TEXT DEFAULT '',
                school_tier TEXT DEFAULT '',
                degree TEXT DEFAULT '',
                degree_source TEXT DEFAULT '',
                salary_base_monthly REAL,
                salary_months INTEGER,
                signing_bonus REAL,
                stock TEXT,
                total_compensation REAL,
                confidence REAL DEFAULT 0.5,
                evidence_text TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                detail_url TEXT DEFAULT '',
                author_hash TEXT DEFAULT '',
                first_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                UNIQUE(content_id, event_type, event_date)
            )
        """)

        # 抓取进度
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crawl_progress (
                topic_uuid TEXT PRIMARY KEY,
                topic_name TEXT,
                last_page INTEGER DEFAULT 0,
                total_records INTEGER DEFAULT 0,
                last_crawl_time TEXT,
                is_active INTEGER DEFAULT 1,
                error_info TEXT
            )
        """)

        # 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_company ON recruit_events(company)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON recruit_events(event_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_role ON recruit_events(role)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_topic ON raw_records(topic_uuid)")

        self.conn.commit()

    def save_raw_record(self, content_id: str, topic_uuid: str, content_type: str,
                        raw_json: dict, title: str, content: str,
                        show_time: Optional[int], create_time: Optional[int],
                        company_name: str, detail_url: str = "") -> bool:
        """保存原始记录，返回是否为新记录"""
        now = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT content_id FROM raw_records WHERE content_id = ?",
            (content_id,)
        )
        exists = cur.fetchone()

        if exists:
            cur.execute("""
                UPDATE raw_records SET
                    last_updated = ?, raw_json = ?, title = ?,
                    content = ?, show_time = ?, create_time = ?,
                    company_name = ?, detail_url = ?
                WHERE content_id = ?
            """, (now, json.dumps(raw_json, ensure_ascii=False),
                  title, content, show_time, create_time,
                  company_name, detail_url, content_id))
            self.conn.commit()
            return False  # 已存在
        else:
            cur.execute("""
                INSERT INTO raw_records
                (content_id, topic_uuid, content_type, raw_json, title,
                 content, show_time, create_time, company_name,
                 detail_url, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (content_id, topic_uuid, content_type,
                  json.dumps(raw_json, ensure_ascii=False),
                  title, content, show_time, create_time,
                  company_name, detail_url, now, now))
            self.conn.commit()
            return True  # 新记录

    def save_event(self, event: dict) -> bool:
        """保存招聘事件，返回是否为新事件"""
        now = datetime.now().isoformat()
        cur = self.conn.cursor()

        # 检查唯一约束
        cur.execute("""
            SELECT id FROM recruit_events
            WHERE content_id = ? AND event_type = ? AND event_date = ?
        """, (event["content_id"], event["event_type"], event.get("event_date", "")))
        exists = cur.fetchone()

        if exists:
            cur.execute("""
                UPDATE recruit_events SET
                    company=?, business_group=?, role=?, role_category=?,
                    location=?, cohort=?, event_date_source=?,
                    source_publish_time=?, school=?, school_tier=?,
                    degree=?, degree_source=?, salary_base_monthly=?,
                    salary_months=?, signing_bonus=?, stock=?,
                    total_compensation=?, confidence=?, evidence_text=?,
                    detail_url=?, quality_score=?, relevance_score=?,
                    validity_score=?, composite_score=?, last_updated=?
                WHERE id=?
            """, (
                event.get("company", ""), event.get("business_group", ""),
                event.get("role", ""), event.get("role_category", ""),
                event.get("location", ""), event.get("cohort", ""),
                event.get("event_date_source", ""),
                event.get("source_publish_time", ""),
                event.get("school", ""), event.get("school_tier", ""),
                event.get("degree", ""), event.get("degree_source", ""),
                event.get("salary_base_monthly"),
                event.get("salary_months"),
                event.get("signing_bonus"),
                event.get("stock"),
                event.get("total_compensation"),
                event.get("confidence", 0.5),
                event.get("evidence_text", ""),
                event.get("detail_url", ""),
                event.get("quality_score", 0),
                event.get("relevance_score", 0),
                event.get("validity_score", 0),
                event.get("composite_score", 0),
                now, exists[0]
            ))
            self.conn.commit()
            return False
        else:
            cur.execute("""
                INSERT INTO recruit_events
                (content_id, topic_uuid, company, business_group, role,
                 role_category, location, cohort, event_type, event_date,
                 event_date_source, source_publish_time, school, school_tier,
                 degree, degree_source, salary_base_monthly, salary_months,
                 signing_bonus, stock, total_compensation, confidence,
                 evidence_text, source_url, detail_url, author_hash,
                 quality_score, relevance_score, validity_score, composite_score,
                 first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.get("content_id", ""), event.get("topic_uuid", ""),
                event.get("company", ""), event.get("business_group", ""),
                event.get("role", ""), event.get("role_category", ""),
                event.get("location", ""), event.get("cohort", ""),
                event.get("event_type", ""), event.get("event_date", ""),
                event.get("event_date_source", ""),
                event.get("source_publish_time", ""),
                event.get("school", ""), event.get("school_tier", ""),
                event.get("degree", ""), event.get("degree_source", ""),
                event.get("salary_base_monthly"),
                event.get("salary_months"),
                event.get("signing_bonus"),
                event.get("stock"),
                event.get("total_compensation"),
                event.get("confidence", 0.5),
                event.get("evidence_text", ""),
                event.get("source_url", ""),
                event.get("detail_url", ""),
                event.get("author_hash", ""),
                event.get("quality_score", 0),
                event.get("relevance_score", 0),
                event.get("validity_score", 0),
                event.get("composite_score", 0),
                now, now
            ))
            self.conn.commit()
            return True

    def get_crawl_progress(self, topic_uuid: str) -> Optional[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM crawl_progress WHERE topic_uuid = ?", (topic_uuid,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_crawl_progress(self, topic_uuid: str, topic_name: str,
                               page: int, total_records: int,
                               error_info: str = ""):
        now = datetime.now().isoformat()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO crawl_progress
            (topic_uuid, topic_name, last_page, total_records,
             last_crawl_time, error_info)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic_uuid) DO UPDATE SET
                last_page = excluded.last_page,
                total_records = excluded.total_records,
                last_crawl_time = excluded.last_crawl_time,
                error_info = excluded.error_info
        """, (topic_uuid, topic_name, page, total_records, now, error_info))
        self.conn.commit()

    def get_events_by_company(self, company: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM recruit_events
            WHERE company LIKE ? OR company LIKE ?
            ORDER BY event_date DESC
        """, (f"%{company}%", f"{company}%"))
        return [dict(r) for r in cur.fetchall()]

    def get_all_companies(self) -> list[str]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT company FROM recruit_events
            ORDER BY company
        """)
        return [r["company"] for r in cur.fetchall()]

    def search_events(self, keyword: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM recruit_events
            WHERE company LIKE ? OR role LIKE ? OR evidence_text LIKE ?
            ORDER BY event_date DESC
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
        return [dict(r) for r in cur.fetchall()]

    def get_events_by_type(self, event_type: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM recruit_events
            WHERE event_type = ?
            ORDER BY event_date DESC
        """, (event_type,))
        return [dict(r) for r in cur.fetchall()]

    def get_low_confidence_events(self, threshold: float = 0.5) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM recruit_events
            WHERE confidence < ?
            ORDER BY confidence ASC
        """, (threshold,))
        return [dict(r) for r in cur.fetchall()]

    def get_stats(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM raw_records")
        raw_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM recruit_events")
        event_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(DISTINCT company) as cnt FROM recruit_events")
        company_count = cur.fetchone()["cnt"]
        cur.execute("""
            SELECT event_type, COUNT(*) as cnt
            FROM recruit_events GROUP BY event_type ORDER BY cnt DESC
        """)
        type_dist = {r["event_type"]: r["cnt"] for r in cur.fetchall()}
        return {
            "raw_records": raw_count,
            "recruit_events": event_count,
            "companies": company_count,
            "event_type_distribution": type_dist,
        }

    def close(self):
        self.conn.close()
