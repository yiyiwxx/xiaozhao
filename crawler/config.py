"""
配置管理
"""

# 话题配置
TOPICS = {
    "2026校招": "a8e19fd30bff42188ed032f4fcbf0415",
    "腾讯": "607c9c2a9baf4167a473bef8336b01c4",
    "小红书": "251e3ce2e12a4c6388304b8d5e7c6a75",
    "海康威视": "2182c3aeffcd4f939ea9456af87a5f22",
    "快手": "53edbd2af32640d8a18cf40d918a8696",
    "bilibili": "2148a4bd0a2e4907896c45ab3de6e1be",
    "拼多多": "d67e0649d79547d4b12d5096c14c210e",
    "阿里": "2f0f5a16724649e5b12c17da5f0ddb2c",
    "京东": "85937f655a72493c8850dd3955d6af38",
    "美团": "61d5479676454b868dd85be27fe0a98f",
    "百度": "7be809e4080b41dc82a9a5a6bf11f9cd",
    "小米": "a188329e955d48c589a6f20c71afc583",
    "OPPO": "d5d6496644564673b4636cffd68dc395",
    "vivo": "f27c474f430646aa8bc6c0a9ccf44d78",
    # 薪资与开奖
    "校招薪资": "c6948ebc5fd24f6daa8a3d8b1f7a2c96",
    "腾讯开奖": "073cb099f8fa4c6986bc5702873e52c8",
    "字节开奖": "aa208513b8f04422bf8764691080a6fc",
    "京东开奖": "2fb9396d50434f06a80f956f39df2d58",
    "美团开奖": "4f6ded85a0fe4b5a94068e9eec981a08",
    "快手开奖": "a95b1b74fbb5435187708c23462a7a26",
    "阿里开奖": "12b04c91d4614a9489ec67091d20c6e7",
    "百度开奖": "5e9b909073bd49ad9ae92a35e51140cd",
    "华为开奖": "227d8fc720b6458fac894fac78178ba0",
    "小米开奖": "d695456033214ff6b1f402ca248a6c46",
}

# 爬虫配置
CRAWL_CONFIG = {
    "min_interval": 2.5,       # 最小请求间隔（秒）
    "max_pages": 10,           # 每个话题最多抓取页数
    "page_size": 20,           # 每页记录数
    "request_timeout": 20,     # 请求超时（秒）
    "max_retries": 3,          # 最大重试次数
    "backoff_base": 2,         # 退避基数
    "db_path": "data/nowcoder.db",
    "raw_dir": "data/raw",
    "min_publish_ms": 1735689600000,  # 2025-01-01 00:00:00 UTC 毫秒时间戳
                                      # 设为0则不过滤旧数据
}

# API 端点
API_BASE = "https://gw-c.nowcoder.com/api/sparta/subject/newest-content"
FEED_DETAIL = "https://www.nowcoder.com/feed/main/detail"
DISCUSS_DETAIL = "https://www.nowcoder.com/discuss"

# 请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nowcoder.com/",
    "Origin": "https://www.nowcoder.com",
}
