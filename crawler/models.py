"""
数据模型定义 - 招聘事件结构化提取结果
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
import json


@dataclass
class RecruitEvent:
    """单个招聘事件"""
    company: str                           # 公司名称
    position: str = ""                     # 岗位
    event_type: str = ""                   # 事件类型: 笔试/面试/OC(口头offer)/Offer/开奖/薪资
    event_time: str = ""                   # 事件时间描述 (如 "3.8笔试")
    source_url: str = ""                   # 来源帖子链接
    source_title: str = ""                 # 来源帖子标题
    city: str = ""                         # 城市
    edu_level: str = ""                    # 学历要求/候选人学历
    school: str = ""                       # 学校
    salary_range: str = ""                 # 薪资范围 (如 "20k*15")
    detail: str = ""                       # 补充信息
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompanyTimeline:
    """公司维度的时间线聚合"""
    company: str
    events: list = field(default_factory=list)

    def add_event(self, event: RecruitEvent):
        self.events.append(event)

    def get_stages(self) -> dict:
        """获取该公司的各阶段概况"""
        stages = {}
        for e in self.events:
            if e.event_type not in stages:
                stages[e.event_type] = []
            stages[e.event_type].append(e)
        return stages


class EventStore:
    """事件存储，内存+JSON持久化"""

    def __init__(self, filepath: str = "data/events.json"):
        self.filepath = filepath
        self.events: list[RecruitEvent] = []
        self._load()

    def add(self, event: RecruitEvent):
        self.events.append(event)

    def add_many(self, events: list[RecruitEvent]):
        self.events.extend(events)

    def get_by_company(self, company: str) -> list[RecruitEvent]:
        return [e for e in self.events if company.lower() in e.company.lower()]

    def get_all_companies(self) -> list[str]:
        companies = set()
        for e in self.events:
            for c in e.company.split("/"):
                c = c.strip()
                if c:
                    companies.add(c)
        return sorted(companies)

    def get_timeline(self) -> dict[str, list[RecruitEvent]]:
        """按公司聚合时间线"""
        tl = {}
        for e in self.events:
            for c in e.company.split("/"):
                c = c.strip()
                if not c:
                    continue
                if c not in tl:
                    tl[c] = []
                tl[c].append(e)
        return tl

    def get_by_event_type(self, event_type: str) -> list[RecruitEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def search(self, keyword: str) -> list[RecruitEvent]:
        kw = keyword.lower()
        return [
            e for e in self.events
            if kw in e.company.lower()
            or kw in e.position.lower()
            or kw in e.detail.lower()
        ]

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    self.events.append(RecruitEvent(**item))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in self.events],
                f,
                ensure_ascii=False,
                indent=2,
            )
