"""
阶段三：结构化事件提取引擎
将原始帖子内容提取为结构化的招聘事件，含置信度评估
"""

import re
import hashlib
from datetime import datetime
from typing import Optional


# ========== 公司与业务群别名 ==========
COMPANY_ALIAS = {
    # 腾讯
    "腾讯": "腾讯", "鹅厂": "腾讯", "WXG": "腾讯", "PCG": "腾讯",
    "IEG": "腾讯", "CSIG": "腾讯", "TEG": "腾讯", "CDG": "腾讯",
    "企微": "腾讯", "微信": "腾讯", "QQ": "腾讯",
    # 字节
    "字节": "字节跳动", "字节跳动": "字节跳动", "抖音": "字节跳动",
    "TikTok": "字节跳动", "飞书": "字节跳动", "火山引擎": "字节跳动",
    "今日头条": "字节跳动",
    # 阿里
    "阿里": "阿里巴巴", "阿里巴巴": "阿里巴巴", "蚂蚁": "蚂蚁集团",
    "蚂蚁集团": "蚂蚁集团", "菜鸟": "菜鸟", "盒马": "盒马",
    "阿里云": "阿里云", "高德": "高德",
    # 拼多多
    "PDD": "拼多多", "pdd": "拼多多", "拼多多": "拼多多",
    "多多": "拼多多",
    # 小红书
    "xhs": "小红书", "小红书": "小红书",
    # 快手
    "手子": "快手", "快手": "快手", "慢脚": "快手",
    # 美团
    "美团": "美团", "大众点评": "美团",
    # 哔哩哔哩
    "小破站": "哔哩哔哩", "b站": "哔哩哔哩", "B站": "哔哩哔哩",
    "哔哩哔哩": "哔哩哔哩",
    # 华为
    "华为": "华为", "华子": "华为", "荣耀": "荣耀",
    # 小米
    "小米": "小米", "红米": "小米", "xiaomi": "小米", "Xiaomi": "小米",
    # OPPO/vivo
    "OPPO": "OPPO", "vivo": "vivo",
    # 百度
    "百度": "百度", "小度": "百度",
    # 京东
    "京东": "京东", "京东云": "京东",
    # 网易
    "网易": "网易", "网易游戏": "网易", "有道": "网易",
    # 新能源车
    "蔚来": "蔚来", "小鹏": "小鹏", "理想": "理想",
    "比亚迪": "比亚迪", "BYD": "比亚迪",
    # 其他互联网/科技
    "科大讯飞": "科大讯飞",
    "SHEIN": "SHEIN", "希音": "SHEIN",
    "米哈游": "米哈游", "鹰角": "鹰角", "叠纸": "叠纸",
    "莉莉丝": "莉莉丝",
    "中兴": "中兴",
    "大疆": "大疆", "DJI": "大疆",
    "TP-LINK": "TP-LINK", "Tplink": "TP-LINK",
    "普联技术": "TP-LINK", "普联": "TP-LINK",
    "海康威视": "海康威视", "海康": "海康威视",
    "深信服": "深信服",
    "广联达": "广联达",
    "商汤": "商汤", "旷视": "旷视",
    "地平线": "地平线",
    "Momenta": "Momenta",
    "元戎启行": "元戎启行",
    "佑驾创新": "佑驾创新",
    "Thoughtworks": "Thoughtworks",
    "宁德时代": "宁德时代",
    "美的": "美的", "格力": "格力",
    "携程": "携程",
    "微众银行": "微众银行", "招银网络": "招银网络",
    "中金": "中金",
    # 电子/制造/新公司
    "TCL": "TCL", "tcl": "TCL", "TCL实业": "TCL", "TCL科技": "TCL",
    "新凯来": "新凯来",
    "青岛芯恩": "芯恩", "芯恩": "芯恩",
    "创维": "创维", "创维数字": "创维",
    "中广核": "中广核",
    # 金融/科技
    "恒生电子": "恒生电子",
    "北方华创": "北方华创",
    "壁仞科技": "壁仞科技",
    "迪普科技": "迪普科技",
    "汇川": "汇川", "汇川技术": "汇川",
    "北部湾港集团": "北部湾港集团",
    # 自动驾驶/芯片
    "卓驭": "卓驭", "卓驭科技": "卓驭",
    "速腾聚创": "速腾聚创",
    "中芯": "中芯", "中芯国际": "中芯",
    "华虹": "华虹", "华虹半导体": "华虹",
    "武汉新芯": "武汉新芯",
    # 互联网/外包
    "虾皮": "Shopee", "Shopee": "Shopee", "shopee": "Shopee",
    "佰钧成": "佰钧成",
    "路特创新": "路特创新",
}

# 业务群前缀提取
BG_PATTERNS = [
    (r'(WXG|PCG|IEG|CSIG|TEG|CDG)', lambda m: m.group(1)),
    (r'(阿里云|蚂蚁|菜鸟|盒马|高德|本地生活|达摩院|平头哥)', lambda m: m.group(1)),
    (r'(抖音|飞书|火山引擎|TikTok|今日头条)', lambda m: m.group(1)),
    (r'(企业微信|微信|QQ)', lambda m: m.group(1)),
    (r'(京东云|京东零售|京东物流|京东科技)', lambda m: m.group(1)),
    (r'(网易游戏|网易有道|网易云音乐)', lambda m: m.group(1)),
    (r'(小米汽车|小米手机|红米)', lambda m: m.group(1)),
]


# ========== 岗位分类 ==========
ROLE_CATEGORIES = {
    "产品": ["产品经理", "AI产品经理", "商业产品经理", "数据产品经理",
             "技术产品经理", "用户产品经理", "产品运营", "产品助理"],
    "技术": ["后端", "前端", "客户端", "测试", "测试开发", "运维",
             "算法", "AI", "NLP", "计算机视觉", "推荐", "搜索",
             "数据开发", "数据分析", "数据仓库", "大数据",
             "嵌入式", "硬件", "FPGA",
             "Java", "C++", "Go", "Python", "Rust",
             "安全", "渗透", "基础架构", "后台", "服务端"],
    "设计": ["UI", "UX", "交互设计", "视觉设计", "用户研究",
             "产品设计", "体验设计", "动效设计"],
    "运营": ["运营", "新媒体", "内容运营", "用户运营", "活动运营",
             "社区运营", "电商运营"],
    "市场": ["市场", "营销", "品牌", "公关", "广告", "商务"],
    "销售": ["销售", "客户经理", "售前", "渠道", "BD"],
    "职能": ["HR", "人力", "财务", "法务", "行政", "战略", "投资",
             "采购", "供应链", "内控"],
}

ROLE_KEYWORDS = []
for cat, roles in ROLE_CATEGORIES.items():
    for role in roles:
        ROLE_KEYWORDS.append((role, cat))

# 按长度降序排列，优先匹配长词
ROLE_KEYWORDS.sort(key=lambda x: -len(x[0]))


# ========== 学历与学校 ==========
# 低置信度学校（玩笑/占位）
LOW_CONFIDENCE_SCHOOLS = [
    "门头沟学院", "蚌埠坦克学院", "第一拖拉机制造厂拖拉机学院",
    "五道口职业技术学院", "中关村文理学院",
]

SCHOOL_TIERS = {
    "清北": ["清华", "北大"],
    "C9": ["浙大", "上交", "复旦", "南大", "哈工大", "西交", "中科大"],
    "华五": ["浙大", "上交", "复旦", "南大", "中科大"],
    "985": ["武大", "华科", "中山", "北航", "北理", "人大", "同济",
            "南开", "天大", "东南", "华工", "厦大", "北师", "国防科大",
            "川大", "山大", "吉大", "中南", "大连理工", "重大",
            "电子科大", "西工大", "华南理工", "湖大", "东北大学"],
    "211": ["北邮", "西电", "南航", "南理", "北交", "北科",
            "北工大", "华东理工", "东华", "上大", "苏大", "南师",
            "中传", "北外", "上外", "央财", "上财", "对外经贸",
            "西南交大", "西南财大", "武汉理工", "华中师范",
            "暨大", "华师"],
    "海外": ["CMU", "MIT", "Stanford", "Berkeley", "Harvard", "Yale",
             "Princeton", "Cambridge", "Oxford", "Imperial",
             "UCL", "LSE", "Columbia", "Cornell", "UCLA",
             "NYU", "USC", "UCB", "UCSD", "UIUC", "Gatech",
             "港大", "港科", "港中文", "港城", "港理",
             "NUS", "NTU"],
}

DEGREE_KEYWORDS = [
    ("博士", "博士"), ("硕士", "硕士"), ("研究生", "硕士"),
    ("本科", "本科"),
    ("大专", "大专"), ("专科", "大专"),
    ("双非", ""), ("985", ""), ("211", ""),
    ("海归", ""), ("海本", ""), ("海硕", ""),
    ("C9", ""),
]


# ========== 事件类型映射 ==========
EVENT_TYPE_PATTERNS = [
    # 需要有明确日期的事件
    (r'(\d{1,2}[\./\-]\d{1,2})\s*(?:投递|简历|内推)', 'application', '投递'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*(?:简历筛选|筛选中|筛选)', 'resume_screening', '简历筛选'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*(?:笔试|机试|笔试题|笔试时间)', 'written_test', '笔试'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*一面', 'first_interview', '一面'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*二面', 'second_interview', '二面'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*三面', 'third_interview', '三面'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*(?:终面|四面|总监面|主管面|leader面)', 'third_interview', '终面'),
    (r'(\d{1,2}[\./\-]\d{1,2})\s*(?:HR面|hr面|人力)', 'hr_interview', 'HR面'),
    (r'(?:已)?OC|口头Offer|口头 offer', 'oc', 'OC'),
    (r'(Offer|offer|意向书|意向)', 'offer', 'Offer'),
    (r'开奖', 'salary', '开奖'),
    (r'(?:收到|泡)?(?:池子|人才池|排序|录用排序)', 'pool', '泡池子'),
    # 被公司拒: 挂/凉/没过/感谢信/被刷
    (r'(?:感谢信|拒信|挂|凉|没过|被刷|流程终止|简历挂|一面挂|二面挂|三面挂|终面挂)', 'rejected', '被拒'),
    # 我拒公司: 已拒/拒了/已拒绝/准备拒/考虑拒（有Offer但主动放弃）
    (r'(?:已拒|拒了|已拒绝|准备拒|考虑拒|不给A|直接拒|含泪拒|秒拒)', 'declined', '主动拒'),
    (r'(?:复活|被捞|又活了|又约面)', 'revived', '复活'),
]

# 薪资模式
SALARY_PATTERNS = [
    # 带 k 的: 25k*16, 30k*15, 55k*15 (必须带 *，防误吞后续数字)
    (r'(\d+(?:\.\d+)?)\s*[kKk]\s*\*\s*(\d+)', 'base_x_months'),
    # 不带 k 的纯数字: 25.5*16, 30*15 (出现在开奖/薪资语境中)
    # 宽松版: 结尾可以是 薪/月/逗号/句号/空格+中文/字符串结束
    (r'(?:(?:开|月|总|年|给|报)(?:的|了|到)?)?\s*(\d+(?:\.\d+)?)\s*\*\s*(\d+)\s*(?:[薪月]|[，,。.\s\u4e00-\u9fff]|$)', 'base_x_months'),
    # 月薪: 25k
    (r'月薪[：:\s]*(\d+(?:\.\d+)?)\s*[kKk]', 'monthly_k'),
    # 纯数字+k 后缀 (anywhere in salary context)
    (r'(?<!\d)(\d+(?:\.\d+)?)\s*[kKk](?:\s|$|[，。、！？)）])', 'monthly_k'),
    # 总包/年包: 总包45w, 年包64w
    (r'总包[：:\s]*(\d+)[万Ww]', 'total_wan'),
    (r'年包[：:\s]*(\d+)[万Ww]', 'total_wan'),
    (r'(\d+)[万Ww][年每年的包]', 'total_wan'),
    # 签字费
    (r'签字费[：:\s]*(\d+)[万Ww]', 'signing_bonus'),
    # 股票
    (r'股票[：:\s]*(?:四年)?(\d+)[万Ww]', 'stock'),
    # 薪资范围: 40-55k
    (r'(\d+)[kK]\s*[-~]\s*(\d+)[kK]', 'range_k'),
    # 普通数字*数字: 25.5*16, 33.5*19, 22*15 等薪资表达（无k前缀）
    (r'(?<!\d)(\d+(?:\.\d+)?)\s*\*\s*(\d+)\s*(?:[薪月]|$)', 'base_x_months'),
]


def normalize_company(text: str) -> tuple[str, str]:
    """标准化公司名，返回 (标准公司名, 业务群)
    
    改进: 匹配到多家公司时，取文本中最先出现的那家。
    """
    bg = ""
    for pattern, extractor in BG_PATTERNS:
        m = re.search(pattern, text)
        if m:
            bg = extractor(m)
            break

    # 找出所有别名匹配，记录 (标准名, 匹配原文, 位置)
    matches = []
    for alias, std_name in COMPANY_ALIAS.items():
        idx = text.find(alias)
        if idx >= 0:
            matches.append((idx, len(alias), std_name))

    # 按出现位置排序，取最先出现的
    if matches:
        matches.sort(key=lambda x: x[0])  # 按位置排序
        return matches[0][2], bg

    # 通用模式匹配（同上）
    BAD_PREFIXES = {
        "你", "我", "他", "她", "它", "这", "那", "哪",
        "我们", "你们", "他们", "她们", "它们",
        "这个", "那个", "哪个", "这些", "那些", "哪些",
        "什么", "怎么", "为什么", "如何", "怎样",
        "已经", "正在", "可以", "应该", "需要", "能够",
        "没有", "不是", "就是", "还是", "只是", "但是",
        "因为", "所以", "如果", "虽然", "而且", "或者",
        "目前", "现在", "当时", "最近", "刚刚",
        "打算", "考虑", "准备", "开始", "继续",
        "去了", "拿了", "给了", "做了", "写了",
        "有人", "有些", "所有", "其中", "里面",
        "包括", "比如", "例如", "作为", "来自",
        "芯片", "软件", "硬件", "系统", "平台",
        "去", "本地", "对方", "这边",
        "一些", "部分", "多数", "少数", "大量",
    }
    BAD_INFIX = {
        "的", "了", "在", "是", "有", "和", "与", "或",
        "被", "把", "将", "从", "到", "对", "为",
    }

    for m in re.finditer(r'([\u4e00-\u9fa5]{2,6})(?:公司|集团)', text):
        name = m.group(1)
        if any(name.startswith(bp) for bp in BAD_PREFIXES):
            continue
        if any(w in name for w in BAD_INFIX):
            continue
        return name, bg

    return "", bg


def classify_role(text: str) -> tuple[str, str]:
    """分类岗位，返回 (role_name, role_category)"""
    for role, cat in ROLE_KEYWORDS:
        if re.search(role, text):
            return role, cat
    return "", "未知"


def extract_event_date(text: str, publish_time_ms: Optional[int]) -> tuple[str, str]:
    """
    从正文提取事件日期
    返回 (date_str, source)  date_str 格式 YYYY-MM-DD
    source: 'text' 来自正文, 'publish_time' 来自发布时间
    校验: month 1-12, day 1-31，无效则跳过
    改进: 如果提取的日期来自 current_year 但比发布时间还晚 3 个月，
          则减去 1 年（防止跨年帖子错误地标注到未来）
    """
    now = datetime.now()
    current_year = now.year

    # 获取发布时间
    pub_dt = None
    if publish_time_ms:
        try:
            pub_dt = datetime.fromtimestamp(publish_time_ms / 1000)
        except (OSError, ValueError):
            pass

    # 尝试多种日期格式
    patterns = [
        (r'(\d{4})[年/\-\.](\d{1,2})[月/\-\.](\d{1,2})', lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r'(\d{1,2})月(\d{1,2})[日号]', lambda m: (current_year, int(m.group(1)), int(m.group(2)))),
        (r'(?<!\d)(\d{1,2})[\./\-](\d{1,2})(?!\s*[kK]\d|\s*\*)', lambda m: (current_year, int(m.group(1)), int(m.group(2)))),
    ]

    for pattern, extractor in patterns:
        for m in re.finditer(pattern, text):
            try:
                year, month, day = extractor(m)
                if not (1 <= month <= 12 and 1 <= day <= 31):
                    continue

                # 对于自动填充 current_year 的日期，检查是否应该减 1 年
                if year == current_year and pub_dt:
                    candidate = datetime(year, month, day)
                    # 如果候选日期比发布时间晚超过 90 天，说明可能跨年了
                    delta = (candidate - pub_dt).days
                    if delta > 90:
                        year -= 1
                        # 减完后重新验证
                        try:
                            candidate = datetime(year, month, day)
                        except ValueError:
                            continue

                return f"{year:04d}-{month:02d}-{day:02d}", 'text'
            except (ValueError, IndexError, AttributeError):
                continue

    # 回退到发布时间
    if publish_time_ms:
        try:
            dt = datetime.fromtimestamp(publish_time_ms / 1000)
            return dt.strftime("%Y-%m-%d"), 'publish_time'
        except (OSError, ValueError):
            pass

    return "", ""


def extract_salary(text: str) -> dict:
    """提取薪资信息"""
    result = {
        "salary_base_monthly": None,
        "salary_months": None,
        "signing_bonus": None,
        "stock": None,
        "total_compensation": None,
    }

    # 用列表收集所有 base_x_months 匹配，最后取最优
    base_x_months_candidates = []
    monthly_k_candidates = []
    best_total = None

    for pattern, ptype in SALARY_PATTERNS:
        for m in re.finditer(pattern, text):
            if ptype == 'base_x_months':
                try:
                    base = float(m.group(1))
                    months_raw = int(m.group(2))
                    # 过滤：月数 > 24 说明是年份误捕（如 "26k*2026 届"）
                    if months_raw > 24:
                        continue
                    tc = round(base * months_raw / 10, 2)
                    base_x_months_candidates.append((base, months_raw, tc))
                except (ValueError, IndexError):
                    pass

            elif ptype == 'monthly_k':
                try:
                    monthly_k_candidates.append(float(m.group(1)))
                except ValueError:
                    pass

            elif ptype == 'total_wan':
                try:
                    v = float(m.group(1))
                    if best_total is None or v > best_total:
                        best_total = v
                except ValueError:
                    pass

            elif ptype == 'signing_bonus':
                try:
                    result["signing_bonus"] = float(m.group(1))
                except ValueError:
                    pass

            elif ptype == 'stock':
                result["stock"] = m.group(1)

            elif ptype == 'range_k':
                try:
                    low = float(m.group(1))
                    high = float(m.group(2))
                    avg = round((low + high) / 2, 1)
                    monthly_k_candidates.append(avg)
                except ValueError:
                    pass

    # 择优录取: base_x_months 取总包最大的（排除房补/津贴等小额项）
    # 过滤: base < 5k 的不可能是主薪资（2k*12 是房补不是工资）
    base_x_months_candidates = [(b, m, t) for b, m, t in base_x_months_candidates if b >= 5]

    if base_x_months_candidates:
        # 按 product(总包) 降序，取最大的
        base_x_months_candidates.sort(key=lambda x: x[2], reverse=True)
        best_base, best_months, best_tc = base_x_months_candidates[0]
        result["salary_base_monthly"] = best_base
        result["salary_months"] = best_months
        result["total_compensation"] = best_tc if best_total is None else best_total
    elif best_total is not None:
        result["total_compensation"] = best_total

    # monthly_k: 取最大值（过滤房补等小额值）
    monthly_k_candidates = [v for v in monthly_k_candidates if v >= 5]
    if monthly_k_candidates and result["salary_base_monthly"] is None:
        result["salary_base_monthly"] = max(monthly_k_candidates)

    return result


def extract_education(text: str, education_info: str = "",
                       auth_display: str = "") -> dict:
    """提取学历信息，返回 {school, school_tier, degree, degree_source, confidence}"""
    result = {
        "school": "",
        "school_tier": "",
        "degree": "",
        "degree_source": "",
        "confidence": 0.0,
    }

    full_text = f"{education_info} {auth_display} {text}"

    # 检查低置信度学校
    for ls in LOW_CONFIDENCE_SCHOOLS:
        if ls in full_text:
            result["school"] = ls
            result["degree_source"] = "self_reported"
            return result

    # 学校匹配
    found_school = ""
    found_tier = ""
    for tier, schools in SCHOOL_TIERS.items():
        for s in schools:
            if s in full_text:
                # 优先取更长的匹配
                if len(s) > len(found_school):
                    found_school = s
                    found_tier = tier

    # 学位匹配
    found_degree = ""
    found_degree_source = ""
    for kw, degree in DEGREE_KEYWORDS:
        if kw in full_text:
            if "985" in full_text or "211" in full_text or "双非" in full_text:
                found_degree_source = "self_reported"
            else:
                found_degree_source = "self_reported"
            if degree:
                found_degree = degree

    # 认证信息（高置信度）
    if education_info and found_school:
        result["degree_source"] = "verified"
        result["confidence"] = 1.0
    elif found_school or found_degree:
        result["degree_source"] = "self_reported"
        result["confidence"] = 0.7

    result["school"] = found_school
    result["school_tier"] = found_tier
    result["degree"] = found_degree
    return result


def extract_city(text: str) -> str:
    """提取城市"""
    cities = [
        "北京", "上海", "深圳", "广州", "杭州", "成都", "南京",
        "武汉", "西安", "重庆", "长沙", "苏州", "合肥", "天津",
        "厦门", "青岛", "大连", "宁波", "珠海", "东莞", "佛山",
        "郑州", "济南", "沈阳", "昆明", "南昌", "无锡",
    ]
    found = [c for c in cities if c in text]
    return found[0] if found else ""


def extract_cohort(text: str) -> str:
    """提取校招届数"""
    m = re.search(r'(20\d{2})\s*届', text)
    if m:
        return f"{m.group(1)}届"
    m = re.search(r'(20\d{2})\s*校招', text)
    if m:
        return f"{m.group(1)}届"
    return ""


def compute_confidence(event_type: str, event_date_source: str,
                       has_company: bool, has_role: bool,
                       evidence_text: str) -> float:
    """
    置信度评估
    0.90+: 正文明确写出公司、阶段和事件日期
    0.75-0.89: 阶段明确，事件日期来自发布时间
    0.50-0.74: 内容暗示进展
    0.50以下: 较大歧义
    """
    score = 0.3  # 基础分

    if has_company:
        score += 0.25
    if has_role:
        score += 0.1

    if event_date_source == 'text':
        score += 0.25
    elif event_date_source == 'publish_time':
        score += 0.15

    # 事件类型的明确度
    if event_type in ('oc', 'offer', 'salary'):
        score += 0.15
    elif event_type in ('written_test', 'first_interview', 'second_interview', 'third_interview'):
        score += 0.1
    elif event_type in ('pool', 'rejected', 'revived'):
        score += 0.05
    elif event_type == 'declined':
        score += 0.15  # 主动拒说明有Offer，信息可信度高

    # 证据文本长度和明确度
    if len(evidence_text) > 20:
        score += 0.05
    if any(kw in evidence_text for kw in ["已", "完成", "收到", "过了", "通过"]):
        score += 0.05

    return round(min(score, 1.0), 2)


def extract_events(title: str, content: str, topic_uuid: str,
                    content_id: str = "", publish_time_ms: Optional[int] = None,
                    education_info: str = "", auth_display: str = "",
                    detail_url: str = "", author_id: str = "") -> list[dict]:
    """
    从帖子标题+内容中提取所有招聘事件
    返回事件字典列表
    """
    full_text = f"{title}\n{content}"[:3000]

    # 公司
    company, business_group = normalize_company(full_text)
    if not company:
        return []  # 没有公司信息的帖子无法确定招聘事件

    # ===== 广告预过滤 =====
    # 强广告信号: 含这些关键词的直接跳过，不产生任何事件
    ad_strong_signals = [
        r'内推码\s*[A-Za-z0-9]{4,}',   # 内推码 ZSXZ0010
        r'专属内推',                     # 专属内推
        r'扫码.*投递',                   # 扫码投递
        r'内推码直通',                   # 内推码直通
        r'填写内推码',                   # 填写内推码
    ]
    if any(re.search(p, full_text) for p in ad_strong_signals):
        return []

    # 弱广告信号累计检查: 多个弱信号同时出现才跳过
    ad_weak_signals = [
        r'(内推|校招|招聘|春招|秋招).*?(内推码|链接|方式|通道|入口|公众号)',
        r'(截止时间|招满即止|手慢|名额有限|限时)',
        r'#[a-zA-Z0-9\u4e00-\u9fa5]+(求职|校招|内推|offer|找工作)',
        r'(六险一金|IPO股权|子女教育|人才计划)',
        r'(应届生offer|offer#|offer直达)',
        r'(公众号|关注.*公众号|后台回复)',
    ]
    weak_hits = sum(1 for p in ad_weak_signals if re.search(p, full_text))
    if weak_hits >= 2:  # 命中 2 个以上弱信号，认为是广告
        return []

    # 岗位
    role, role_category = classify_role(full_text)

    # 届数
    cohort = extract_cohort(full_text)

    # 城市
    location = extract_city(full_text)

    # 薪资
    salary_info = extract_salary(full_text)

    # 学历
    edu_info = extract_education(full_text, education_info, auth_display)

    # 事件识别
    events = []
    seen_types = set()

    for pattern, event_type, event_label in EVENT_TYPE_PATTERNS:
        for m in re.finditer(pattern, full_text):
            if event_type == 'salary' and event_label == '开奖':
                # 对于"开奖"，尝试提取具体日期
                date_str, date_source = extract_event_date(full_text, publish_time_ms)
            else:
                # 对于有日期的模式
                date_str, date_source = extract_event_date(m.group(0), publish_time_ms)
                if not date_str:
                    date_str, date_source = extract_event_date(full_text, publish_time_ms)

            # 去重: 同一 content_id 中相同 event_type 只保留一次
            if event_type in seen_types:
                continue
            seen_types.add(event_type)

            confidence = compute_confidence(
                event_type, date_source,
                bool(company), bool(role),
                m.group(0) if m else ""
            )

            # 需要区分"已经面试"和"询问面试内容"
            text_before = full_text[:max(0, m.start())][-200:]
            is_asking = any(kw in text_before for kw in [
                "请问", "想问", "如何", "怎么", "求问",
                "有了解", "有人知道", "什么情况",
            ])
            if is_asking and event_type in ('first_interview', 'second_interview', 'third_interview'):
                confidence = min(confidence, 0.5)  # 降级，无法确认已完成面试

            # 构建 evidence_text
            start = max(0, m.start() - 30)
            end = min(len(full_text), m.end() + 50)
            evidence = full_text[start:end].strip()
            evidence = re.sub(r'\s+', ' ', evidence)

            # 作者hash（去标识化）
            author_hash = ""
            if author_id:
                author_hash = hashlib.md5(author_id.encode()).hexdigest()[:8]

            event = {
                "company": company,
                "business_group": business_group,
                "role": role,
                "role_category": role_category,
                "location": location,
                "cohort": cohort,
                "event_type": event_type,
                "event_date": date_str,
                "event_date_source": date_source,
                "source_publish_time": datetime.fromtimestamp(publish_time_ms / 1000).isoformat() if publish_time_ms else "",
                "school": edu_info["school"],
                "school_tier": edu_info["school_tier"],
                "degree": edu_info["degree"],
                "degree_source": edu_info["degree_source"],
                "salary_base_monthly": salary_info["salary_base_monthly"],
                "salary_months": salary_info["salary_months"],
                "signing_bonus": salary_info["signing_bonus"],
                "stock": salary_info["stock"],
                "total_compensation": salary_info["total_compensation"],
                "confidence": confidence,
                "evidence_text": evidence[:300],
                "source_url": f"https://gw-c.nowcoder.com/api/sparta/subject/newest-content?uuid={topic_uuid}",
                "detail_url": detail_url,
                "author_hash": author_hash,
                "content_id": content_id,
                "topic_uuid": topic_uuid,
            }
            events.append(event)

    return events
