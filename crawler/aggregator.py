"""
阶段四：聚合输出
生成公司级时间线、岗位筛选、学历统计、薪资分析
"""

import json
from datetime import datetime
from typing import Optional
from crawler.database import Database


class Aggregator:
    def __init__(self, db: Database):
        self.db = db

    def company_timeline(self, company: str) -> dict:
        """生成公司级时间线"""
        events = self.db.get_events_by_company(company)
        if not events:
            return {"company": company, "events": [], "latest_update": ""}

        latest = max(e.get("event_date", "") or "" for e in events)
        updates = max(
            e.get("last_updated", "") or ""
            for e in events if e.get("last_updated")
        )

        # 按日期排序
        sorted_events = sorted(
            events,
            key=lambda e: e.get("event_date", "") or "",
            reverse=True,
        )

        # 学历统计
        schools = set()
        self_reported_tiers = {}
        for e in events:
            if e.get("school"):
                schools.add(e["school"])
            if e.get("school_tier") and e.get("degree_source") == "self_reported":
                t = e["school_tier"]
                self_reported_tiers[t] = self_reported_tiers.get(t, 0) + 1

        # 薪资统计
        salaries = []
        for e in events:
            tc = e.get("total_compensation")
            if tc and tc > 0:
                salaries.append(tc)

        salary_summary = {
            "sample_count": len(salaries),
            "minimum_total_compensation": min(salaries) if salaries else None,
            "maximum_total_compensation": max(salaries) if salaries else None,
            "median_total_compensation": (
                sorted(salaries)[len(salaries) // 2] if salaries else None
            ),
        }

        # 阶段概况
        stage_summary = {}
        for e in sorted_events:
            et = e.get("event_type", "")
            if et not in stage_summary:
                stage_summary[et] = 0
            stage_summary[et] += 1

        return {
            "company": company,
            "latest_update": latest or updates,
            "event_count": len(sorted_events),
            "stage_summary": stage_summary,
            "education_summary": {
                "verified_school_count": len(schools),
                "self_reported_tiers": self_reported_tiers,
            },
            "salary_summary": salary_summary,
            "events": [
                {
                    "date": e.get("event_date", ""),
                    "event": e.get("event_type", ""),
                    "role": e.get("role", ""),
                    "role_category": e.get("role_category", ""),
                    "confidence": e.get("confidence", 0),
                    "evidence": e.get("evidence_text", ""),
                    "detail_url": e.get("detail_url", ""),
                    "location": e.get("location", ""),
                    "salary": f"{e.get('salary_base_monthly', '') or ''}k"
                             + (f"*{e.get('salary_months', '')}" if e.get('salary_months') else ""),
                }
                for e in sorted_events
            ],
        }

    def all_company_timelines(self) -> list[dict]:
        """获取所有公司的时间线"""
        companies = self.db.get_all_companies()
        timelines = []
        for c in companies:
            tl = self.company_timeline(c)
            if tl.get("events"):
                timelines.append(tl)
        # 按最新更新时间排序
        timelines.sort(key=lambda t: t.get("latest_update", ""), reverse=True)
        return timelines

    def filter_by_role(self, role_category: str) -> list[dict]:
        """按岗位分类筛选"""
        events = []
        for company in self.db.get_all_companies():
            for e in self.db.get_events_by_company(company):
                if e.get("role_category") == role_category:
                    events.append(e)
        events.sort(key=lambda e: e.get("event_date", "") or "", reverse=True)
        return events

    def low_confidence_events(self, threshold: float = 0.5) -> list[dict]:
        """待人工复核的低置信度事件"""
        return self.db.get_low_confidence_events(threshold)

    def export_json(self, filepath: str):
        """导出JSON"""
        data = {
            "export_time": datetime.now().isoformat(),
            "stats": self.db.get_stats(),
            "timelines": self.all_company_timelines(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
