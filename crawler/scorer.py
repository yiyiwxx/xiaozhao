"""
三层评分体系

Layer 1: 内容质量评分 (Content Quality)  — 帖子本身的丰富度和细节量
Layer 2: 目标岗位相关度 (Job Relevance)   — 对用户关注岗位/公司的匹配度
Layer 3: 信息有效性评分 (Info Validity)   — 信息是否可靠、可操作、有决策价值

综合分数 = w1 * quality + w2 * relevance + w3 * validity
默认权重: quality=0.3, relevance=0.4, validity=0.3
"""

import re
from typing import Optional
from datetime import datetime


# ==================== 用户目标配置 ====================
# 用户关注的 "目标岗位"，可按需修改
TARGET_ROLES = ["产品经理", "AI产品经理", "产品"]

# 用户关注的 "目标公司"，可按需修改
TARGET_COMPANIES = ["腾讯", "字节跳动", "阿里巴巴", "美团", "拼多多",
                     "快手", "百度", "小红书", "哔哩哔哩"]

# 各层权重 (有效性提到0.35，因为新加入的个人经历/广告检测更具辨别力)
WEIGHTS = {
    "quality": 0.25,
    "relevance": 0.40,
    "validity": 0.35,
}


# ==================== Layer 1: 内容质量评分 ====================

def score_content_quality(title: str, content: str, event: dict) -> float:
    """
    评估帖子的内容质量 (0-100)
    高分: 有具体细节、结构化时间线、薪资信息、面经详情
    低分: 纯提问、纯情绪、一句话帖子
    """
    score = 0.0
    full_text = f"{title or ''} {content or ''}"

    # 1. 内容长度 (0-15分)
    length = len(full_text)
    if length > 2000:
        score += 15
    elif length > 1000:
        score += 12
    elif length > 500:
        score += 8
    elif length > 200:
        score += 4
    else:
        score += 1

    # 2. 有具体日期信息 (0-15分)
    date_patterns = [
        r'\d{1,2}[\./\-]\d{1,2}\s*(?:一面|二面|三面|终面|笔试|面试|HR面|oc|offer)',
        r'\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2}',
        r'\d{1,2}月\d{1,2}[日号]',
        r'TL[：:\s]',
        r'timeline',
    ]
    for p in date_patterns:
        if re.search(p, full_text, re.IGNORECASE):
            score += 3  # 最多15分
    score = min(score, 15 + 0)  # 确保日期部分不超过15

    # 3. 有薪资信息 (0-15分)
    salary_patterns = [
        r'\d+[kK]\s*\*?\s*\d+', r'总包\d+[万Ww]', r'年包\d+[万Ww]',
        r'月薪', r'签字费', r'开奖',
    ]
    for p in salary_patterns:
        if re.search(p, full_text):
            score += 5
            break  # 薪资有提到就给5分
    # 有具体数值再加分
    if event.get("salary_base_monthly") or event.get("total_compensation"):
        score += 10

    # 4. 有具体的面经/经历描述 (0-20分)
    detail_indicators = [
        (r'(一面|二面|三面|终面|HR面).*?(问了|考了|项目|算法|SQL|八股|场景题)', 8),
        (r'(手撕|代码题|算法题|编程题)', 5),
        (r'(自我介绍|项目介绍|实习经历|项目经验)', 5),
        (r'(反问|还有什么问题)', 3),
        (r'(已通过|已过|过了|拿到|收到|感谢信)', 4),
    ]
    for pattern, pts in detail_indicators:
        if re.search(pattern, full_text):
            score += pts

    # 5. 有学历/学校信息 (0-10分)
    if event.get("school") or event.get("degree"):
        score += 5
    if event.get("degree_source") == "verified":
        score += 5

    # 6. 结构完整性 - 有标题且有正文 (0-10分)
    if title and len(title) > 5:
        score += 3
    if content and len(content) > 100:
        score += 3
    # 有明确的结构标记
    if re.search(r'(TL[：:]|时间线|timeline|进度)', full_text, re.IGNORECASE):
        score += 4

    # 7. 扣分项: 纯提问/水帖 (-15分)
    ask_indicators = [
        (r'^(请问|想问|求问|想问一下|有没有人|有木有|求助|跪求)', -8),
        (r'(怎么办|怎么选|该不该|值不值得)', -5),
        (r'^.{0,10}(水帖|水一下|随便聊聊)', -5),
    ]
    for pattern, pts in ask_indicators:
        if re.search(pattern, full_text):
            score += pts

    return round(max(0, min(100, score)), 1)


# ==================== Layer 2: 目标岗位相关度 ====================

def score_job_relevance(event: dict) -> float:
    """
    评估与用户目标岗位的相关度 (0-100)
    基于可配置的目标岗位和目标公司
    """
    score = 0.0

    company = event.get("company", "")
    role = event.get("role", "")
    role_category = event.get("role_category", "")
    event_type = event.get("event_type", "")
    evidence = event.get("evidence_text", "")

    # 1. 公司匹配 (0-30分)
    for tc in TARGET_COMPANIES:
        if tc in company:
            # 完全匹配 +30，部分匹配按比例
            if tc == company:
                score += 30
            else:
                score += 20
            break

    # 2. 岗位匹配 (0-35分)
    for tr in TARGET_ROLES:
        if tr in role or tr.lower() in role.lower():
            score += 35
            break
    else:
        # 如果大类匹配，部分得分
        if role_category == "产品":
            score += 20
        elif role_category == "技术":
            score += 10  # 技术类也有参考价值

    # 3. 事件类型权重 (0-20分)
    # Offer/开奖/薪资 对求职者最有价值
    type_weight = {
        "salary": 20,      # 开奖薪资最重要
        "offer": 18,       # Offer信息
        "oc": 15,          # 口头Offer
        "declined": 15,    # 主动拒 = 有Offer但看不上，含薪资参照价值
        "first_interview": 12,
        "second_interview": 12,
        "third_interview": 12,
        "hr_interview": 10,
        "written_test": 8,
        "rejected": 5,     # 被拒信息也有参考
        "revived": 8,
        "pool": 6,
        "application": 3,
    }
    score += type_weight.get(event_type, 5)

    # 4. 同目标岗位的面经特别加分 (0-15分)
    if any(tr in evidence for tr in TARGET_ROLES):
        score += 10
    if any(tc in evidence for tc in TARGET_COMPANIES):
        score += 5

    return round(max(0, min(100, score)), 1)


# ==================== Layer 3: 信息有效性评分 ====================

def score_info_validity(title: str, content: str, event: dict) -> float:
    """
    评估信息的有效性、可靠性和可操作性 (0-100)
    高分: 真实经历、可验证、有决策价值
    低分: 广告、模板帖、纯情绪、无法验证
    """
    score = 50.0  # 基础中立分
    full_text = f"{title or ''} {content or ''}"

    # 1. 有明确日期 +15分 (从正文提取)
    if event.get("event_date_source") == "text":
        score += 15
    elif event.get("event_date_source") == "publish_time":
        score += 5

    # 2. 事件置信度继承 +20分
    conf = event.get("confidence", 0.5)
    score += conf * 20

    # 3. 证据文本长度 +10分
    ev_len = len(event.get("evidence_text", ""))
    if ev_len > 100:
        score += 10
    elif ev_len > 50:
        score += 5

    # 4. 有具体数值信息 +15分 (高价值信号)
    if event.get("salary_base_monthly"):
        score += 8
    if event.get("total_compensation"):
        score += 7

    # 5. 真实个人经历加分 (+30分)
    # 有个人背景描述
    if re.search(r'(bg|本人|楼主|我\s*(985|211|双非|硕|本|海归))', full_text):
        score += 10
    # 有具体薪资*k*月格式 (真实开奖帖特征)
    if re.search(r'\d+(?:\.\d+)?[kK]\s*\*\s*\d+', full_text):
        score += 10
    # 有面试时间线
    if re.search(r'(一面|二面|三面|HR面).*?(?:面|过|挂|通过|拿到|收到)', full_text):
        score += 10

    # 6. 扣分: 广告/内推帖嫌疑 (-30分起)
    ad_indicators = [
        (r'(内推码|内推链接|内推方式|扫码|加微信|私信我|专属内推)', -12),
        (r'(点击链接|投递链接|投递入口|简历直达)', -8),
        (r'(名额有限|限时|速来|抓紧|手慢|截止时间|招满即止)', -8),
        (r'(附上.*内推)', -8),
        # 招聘帖"福利清单"模式
        (r'(六险一金|IPO股权|子女教育|公寓|人才计划)', -5),
        # hashtag 投递风格
        (r'#[a-zA-Z\u4e00-\u9fa5]+(求职|校招|内推|offer)', -8),
        (r'(应届生offer|offer#|内推码直通)', -8),
        # 连续3个以上不同emoji (广告帖特征)
        (r'(?:[\U0001F300-\U0001FAFF]|[\u2600-\u27BF])\s*(?:[\U0001F300-\U0001FAFF]|[\u2600-\u27BF])\s*(?:[\U0001F300-\U0001FAFF]|[\u2600-\u27BF])', -5),
    ]
    for pattern, pts in ad_indicators:
        if re.search(pattern, full_text):
            score += pts

    # 7. 扣分: 纯情绪无信息 (-15分)
    emotional_patterns = [
        (r'(呜呜|哭了|破防|emo|心态崩了|焦虑死|崩溃)', -5),
        (r'(太难了|好难|好卷|太卷了)', -3),
        (r'!{3,}', -2),   # 连续多个感叹号
    ]
    for pattern, pts in emotional_patterns:
        if re.search(pattern, full_text):
            score += pts

    # 8. 时效性检查: 超过60天的事件降权 (-10分)
    if event.get("event_date"):
        try:
            ev_date = datetime.strptime(event["event_date"][:10], "%Y-%m-%d")
            days_ago = (datetime.now() - ev_date).days
            if days_ago > 60:
                score -= 10
            elif days_ago > 30:
                score -= 5
        except (ValueError, IndexError):
            pass

    # 9. 不是"询问"而是"分享" +10分
    if re.search(r'(以下是|分享|面经|经历|时间线|TL)', full_text, re.IGNORECASE):
        score += 10

    return round(max(0, min(100, score)), 1)


# ==================== 综合评分 ====================

def compute_composite_score(
    title: str,
    content: str,
    event: dict,
    weights: Optional[dict] = None,
) -> dict:
    """
    计算三层综合评分
    返回:
    {
        "quality_score": float,       # 内容质量 0-100
        "relevance_score": float,     # 目标相关度 0-100
        "validity_score": float,      # 信息有效性 0-100
        "composite_score": float,     # 综合加权分 0-100
        "weights_used": dict,         # 使用的权重
    }
    """
    if weights is None:
        weights = WEIGHTS

    quality = score_content_quality(title, content, event)
    relevance = score_job_relevance(event)
    validity = score_info_validity(title, content, event)

    composite = (
        weights["quality"] * quality
        + weights["relevance"] * relevance
        + weights["validity"] * validity
    )

    return {
        "quality_score": quality,
        "relevance_score": relevance,
        "validity_score": validity,
        "composite_score": round(composite, 1),
        "weights_used": weights,
    }


def score_event(title: str, content: str, event: dict) -> dict:
    """
    对单个事件进行完整评分（便捷入口）
    """
    return compute_composite_score(title, content, event)


# ==================== 批量评分 ====================

def score_events(title: str, content: str, events: list[dict]) -> list[dict]:
    """
    对一篇文章提取出的所有事件进行评分
    返回附带了评分字段的事件列表
    """
    scored = []
    for event in events:
        scores = compute_composite_score(title, content, event)
        event.update({
            "quality_score": scores["quality_score"],
            "relevance_score": scores["relevance_score"],
            "validity_score": scores["validity_score"],
            "composite_score": scores["composite_score"],
        })
        scored.append(event)
    return scored


# ==================== 优先级标签 ====================

def priority_label(composite_score: float) -> str:
    """根据综合分数打优先级标签"""
    if composite_score >= 80:
        return "⭐⭐高价值"
    elif composite_score >= 60:
        return "⭐中价值"
    elif composite_score >= 40:
        return "参考"
    else:
        return "低价值/噪音"


# ==================== 测试 ====================

if __name__ == "__main__":
    # 测试用例
    test_events = [
        {
            "title": "字节跳动后端面经",
            "content": (
                "字节跳动后端开发面经\n"
                "TL: 3.15投递 3.20笔试 3.25一面 4.1二面 4.8三面 4.15HR面 4.20 OC\n"
                "一面: 问了Java并发、MySQL索引优化、Redis缓存穿透\n"
                "二面: 手撕LRU、系统设计-短链接\n"
                "三面: 项目深挖、场景题\n"
                "已拿Offer，base北京，25k*15，985硕"
            ),
            "event": {
                "company": "字节跳动", "role": "后端", "role_category": "技术",
                "event_type": "offer", "confidence": 0.95,
                "event_date": "2026-04-20", "event_date_source": "text",
                "salary_base_monthly": 25.0, "total_compensation": 37.5,
                "school": "985硕士", "degree": "硕士", "degree_source": "self_reported",
                "evidence_text": "字节跳动后端开发面经 TL: 3.15投递...已拿Offer，base北京，25k*15",
            },
        },
        {
            "title": "请问腾讯产品经理面试考什么",
            "content": "请问腾讯产品经理面试会问哪些问题？一般有几轮面试？有了解的同学吗？",
            "event": {
                "company": "腾讯", "role": "产品经理", "role_category": "产品",
                "event_type": "first_interview", "confidence": 0.45,
                "event_date": "", "event_date_source": "publish_time",
                "salary_base_monthly": None, "total_compensation": None,
                "school": "", "degree": "", "degree_source": "",
                "evidence_text": "请问腾讯产品经理面试会问哪些问题",
            },
        },
    ]

    print("三层评分测试")
    print("=" * 60)
    for tc in test_events:
        print(f"\n标题: {tc['title']}")
        print(f"内容: {tc['content'][:80]}...")
        scores = compute_composite_score(tc["title"], tc["content"], tc["event"])
        for k, v in scores.items():
            print(f"  {k}: {v}")
        print(f"  优先级: {priority_label(scores['composite_score'])}")
