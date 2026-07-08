"""
校招进度聚合器 - 自动化测试
"""

import os
import sys
import json
import tempfile
import unittest

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.parsers import (
    normalize_company, classify_role, extract_event_date,
    extract_salary, extract_education, extract_city,
    extract_cohort, extract_events, compute_confidence,
)
from crawler.models import RecruitEvent, EventStore


class TestCompanyNormalization(unittest.TestCase):
    """测试公司名标准化"""

    def test_tencent_aliases(self):
        self.assertEqual(normalize_company("腾讯一面")[0], "腾讯")
        self.assertEqual(normalize_company("鹅厂开奖")[0], "腾讯")
        self.assertEqual(normalize_company("WXG后端")[0], "腾讯")

    def test_bytedance_aliases(self):
        self.assertEqual(normalize_company("字节跳动校招")[0], "字节跳动")
        self.assertEqual(normalize_company("抖音电商")[0], "字节跳动")

    def test_business_group(self):
        self.assertEqual(normalize_company("WXG一面")[1], "WXG")
        self.assertEqual(normalize_company("PCG后端")[1], "PCG")

    def test_unknown_company(self):
        self.assertEqual(normalize_company("某不知名厂")[0], "")


class TestRoleClassification(unittest.TestCase):
    """测试岗位分类"""

    def test_product_manager(self):
        role, cat = classify_role("产品经理")
        self.assertEqual(role, "产品经理")
        self.assertEqual(cat, "产品")

    def test_backend(self):
        role, cat = classify_role("后端开发")
        self.assertEqual(role, "后端")
        self.assertEqual(cat, "技术")

    def test_algorithm(self):
        role, cat = classify_role("算法工程师")
        self.assertEqual(role, "算法")
        self.assertEqual(cat, "技术")

    def test_operation(self):
        role, cat = classify_role("运营")
        self.assertEqual(role, "运营")
        self.assertEqual(cat, "运营")


class TestEventDateExtraction(unittest.TestCase):
    """测试日期提取"""

    def test_month_day_format(self):
        date_str, source = extract_event_date("3.19一面", None)
        self.assertEqual(source, "text")
        self.assertTrue(date_str.endswith("-03-19"))

    def test_full_date_format(self):
        date_str, source = extract_event_date("2026年3月19日面试", None)
        self.assertEqual(source, "text")
        self.assertEqual(date_str, "2026-03-19")

    def test_chinese_date(self):
        date_str, source = extract_event_date("6月5日二面", None)
        self.assertEqual(source, "text")
        self.assertTrue(date_str.endswith("-06-05"))

    def test_fallback_to_publish_time(self):
        date_str, source = extract_event_date("今天面试了", 1778000000000)
        self.assertEqual(source, "publish_time")


class TestSalaryExtraction(unittest.TestCase):
    """测试薪资提取"""

    def test_base_x_months(self):
        result = extract_salary("25.5k*16")
        self.assertEqual(result["salary_base_monthly"], 25.5)
        self.assertEqual(result["salary_months"], 16)
        self.assertIsNotNone(result["total_compensation"])

    def test_total_wan(self):
        result = extract_salary("总包45w")
        self.assertEqual(result["total_compensation"], 45)

    def test_no_salary(self):
        result = extract_salary("只是问一下面试经验")
        self.assertIsNone(result["total_compensation"])


class TestEventExtraction(unittest.TestCase):
    """测试完整事件提取"""

    def test_interview_event(self):
        events = extract_events(
            title="字节跳动后端面经",
            content="3.15一面，3.22二面，已OC。985硕，北京，总包40w+",
            topic_uuid="test",
            content_id="test001",
        )
        event_types = {e["event_type"] for e in events}
        self.assertIn("first_interview", event_types)
        self.assertIn("second_interview", event_types)
        # "已OC" 匹配为 OC 事件
        self.assertIn("oc", event_types)
        # 总包薪资信息附在OC事件中
        oc_events = [e for e in events if e["event_type"] == "oc"]
        self.assertTrue(len(oc_events) > 0)
        # 验证薪资信息已被提取
        self.assertEqual(oc_events[0]["total_compensation"], 40)

    def test_salary_event(self):
        events = extract_events(
            title="腾讯开奖",
            content="腾讯开奖了，后台开发，深圳，年包45w",
            topic_uuid="test",
            content_id="test002",
        )
        salary_events = [e for e in events if e["event_type"] == "salary"]
        self.assertTrue(len(salary_events) > 0)
        self.assertEqual(salary_events[0]["total_compensation"], 45)

    def test_asking_vs_done_interview(self):
        """区分询问面试 vs 完成面试"""
        done_events = extract_events(
            title="字节一面",
            content="3.19一面完成了",
            topic_uuid="test",
            content_id="test003",
        )
        asking_events = extract_events(
            title="请问字节一面",
            content="请问字节一面考什么？3.19一面",
            topic_uuid="test",
            content_id="test004",
        )

        done_confidence = [e["confidence"] for e in done_events if e["event_type"] == "first_interview"]
        asking_confidence = [e["confidence"] for e in asking_events if e["event_type"] == "first_interview"]

        if done_confidence and asking_confidence:
            self.assertGreater(done_confidence[0], asking_confidence[0])

    def test_no_company_returns_empty(self):
        events = extract_events(
            title="今天天气真好",
            content="没什么特别的",
            topic_uuid="test",
            content_id="test005",
        )
        self.assertEqual(len(events), 0)


class TestEducationExtraction(unittest.TestCase):
    """测试学历提取"""

    def test_self_reported_985(self):
        result = extract_education("本人985硕士，求面经")
        # "985" 是学历层级描述而非学校名，应出现在 degree 字段
        self.assertEqual(result["degree"], "硕士")
        self.assertEqual(result["degree_source"], "self_reported")

    def test_low_confidence_school(self):
        result = extract_education("门头沟学院路过")
        self.assertEqual(result["school"], "门头沟学院")


class TestConfidenceComputation(unittest.TestCase):
    """测试置信度计算"""

    def test_high_confidence(self):
        score = compute_confidence(
            event_type="first_interview",
            event_date_source="text",
            has_company=True,
            has_role=True,
            evidence_text="3.19一面完成，面试官问了数据库",
        )
        self.assertGreaterEqual(score, 0.80)

    def test_low_confidence(self):
        score = compute_confidence(
            event_type="pool",
            event_date_source="publish_time",
            has_company=False,
            has_role=False,
            evidence_text="有人在池子里吗",
        )
        self.assertLess(score, 0.70)


class TestEventStore(unittest.TestCase):
    """测试事件存储"""

    def setUp(self):
        self.tmpfile = tempfile.mktemp(suffix=".json")
        self.store = EventStore(self.tmpfile)

    def tearDown(self):
        if os.path.exists(self.tmpfile):
            os.remove(self.tmpfile)

    def test_add_and_get(self):
        event = RecruitEvent(
            company="腾讯",
            event_type="offer",
            event_time="2026-03-19",
        )
        self.store.add(event)
        self.assertEqual(len(self.store.get_by_company("腾讯")), 1)

    def test_persistence(self):
        event = RecruitEvent(company="字节跳动", event_type="first_interview")
        self.store.add(event)
        self.store.save()

        store2 = EventStore(self.tmpfile)
        self.assertEqual(len(store2.events), 1)
        self.assertEqual(store2.events[0].company, "字节跳动")

    def test_search(self):
        self.store.add(RecruitEvent(company="腾讯", position="产品经理"))
        self.store.add(RecruitEvent(company="字节跳动", position="后端"))
        results = self.store.search("产品")
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
