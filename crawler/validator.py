"""
阶段一：接口验证
对每个话题只请求第一页，记录 HTTP 状态、Content-Type、是否为有效 JSON。
"""

import json
import sys
import time
import requests
from urllib.parse import urlencode

BASE_URL = "https://gw-c.nowcoder.com/api/sparta/subject/newest-content"

TEST_TOPICS = {
    "2026校招": "a8e19fd30bff42188ed032f4fcbf0415",
    "腾讯": "607c9c2a9baf4167a473bef8336b01c4",
    "美团": "61d5479676454b868dd85be27fe0a98f",
    "字节开奖": "aa208513b8f04422bf8764691080a6fc",
    "腾讯开奖": "073cb099f8fa4c6986bc5702873e52c8",
    "阿里开奖": "12b04c91d4614a9489ec67091d20c6e7",
    "华为开奖": "227d8fc720b6458fac894fac78178ba0",
    "校招薪资": "c6948ebc5fd24f6daa8a3d8b1f7a2c96",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nowcoder.com/",
}


def validate_topic(name: str, uuid: str) -> dict:
    """验证单个话题的API可访问性"""
    url = f"{BASE_URL}?{urlencode({'pageNo': 1, 'uuid': uuid})}"
    result = {
        "topic_name": name,
        "uuid": uuid,
        "http_status": None,
        "content_type": None,
        "is_valid_json": False,
        "is_waf_or_captcha": False,
        "total_records": None,
        "latest_time": None,
        "sample_titles": [],
        "error": None,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        result["http_status"] = resp.status_code
        result["content_type"] = resp.headers.get("Content-Type", "")

        # 检查是否是WAF/验证码页面
        ct = result["content_type"]
        if "text/html" in ct or resp.status_code in (403, 429):
            body_lower = resp.text[:500].lower()
            if any(kw in body_lower for kw in [
                "验证", "captcha", "waf", "access denied",
                "请滑动", "slid", "verify", "安全验证",
            ]):
                result["is_waf_or_captcha"] = True
                result["error"] = f"WAF/验证码拦截 (HTTP {resp.status_code})"
                return result
            if resp.status_code == 429:
                result["error"] = f"限流 (HTTP 429)"
                return result

        # 尝试解析JSON
        try:
            data = resp.json()
            result["is_valid_json"] = True
        except json.JSONDecodeError:
            result["error"] = f"非JSON响应: {resp.text[:200]}"
            return result

        # 解析结构
        if "data" in data:
            d = data["data"]
            if isinstance(d, dict):
                result["total_records"] = d.get("total", 0)
                result["total_page"] = d.get("totalPage", 0)
                result["current"] = d.get("current", 0)

                records = d.get("records", [])
                for r in records[:5]:
                    title = ""
                    # 尝试不同字段获取标题
                    md = r.get("momentData") or {}
                    cd = r.get("contentData") or {}
                    title = md.get("title", "") or cd.get("title", "")
                    show_time = md.get("showTime", "") or cd.get("showTime", "")
                    result["sample_titles"].append({
                        "title": title[:80],
                        "time": show_time,
                    })

                # 获取最新时间
                if records:
                    first = records[0]
                    md = first.get("momentData") or {}
                    cd = first.get("contentData") or {}
                    result["latest_time"] = (
                        md.get("showTime") or cd.get("showTime") or cd.get("createTime") or ""
                    )
        else:
            result["error"] = f"响应缺少data字段: {json.dumps(data, ensure_ascii=False)[:200]}"

    except requests.exceptions.Timeout:
        result["error"] = "请求超时"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"连接失败: {e}"
    except Exception as e:
        result["error"] = f"异常: {e}"

    return result


def main():
    print("=" * 70)
    print("牛客网公开话题API 接口验证报告")
    print(f"验证时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 先验证基本连通性
    print("\n[1] 基础连通性测试")
    try:
        r = requests.get("https://www.nowcoder.com/", headers=HEADERS, timeout=10)
        print(f"    牛客网首页: HTTP {r.status_code}, {len(r.text)} bytes")
    except Exception as e:
        print(f"    牛客网首页: 失败 - {e}")

    print(f"\n[2] 话题API验证 (共{len(TEST_TOPICS)}个话题)\n")

    results = []
    for name, uuid in TEST_TOPICS.items():
        print(f"  ▶ {name} ({uuid[:16]}...)", end=" ")
        sys.stdout.flush()
        result = validate_topic(name, uuid)
        results.append(result)

        status = "✅" if result["is_valid_json"] else "❌"
        reason = result.get("error", "")
        print(f" ✅ HTTP {result['http_status']}", end="")
        if result["is_valid_json"]:
            latest = result['latest_time']
            if isinstance(latest, str):
                latest_str = latest[:16]
            else:
                latest_str = str(latest)
            print(f" | {result['total_records']}条 | 最新: {latest_str}")
            for s in result["sample_titles"]:
                print(f"       ├ {s['title']}")
                print(f"       └ {s['time']}")
        else:
            print(f" | {reason}")
        time.sleep(1)  # 礼貌间隔

    # 汇总
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    valid = sum(1 for r in results if r["is_valid_json"])
    waf = sum(1 for r in results if r["is_waf_or_captcha"])
    total_records = sum(r["total_records"] or 0 for r in results if r["total_records"])
    print(f"  有效JSON响应: {valid}/{len(results)}")
    print(f"  WAF/验证码: {waf}/{len(results)}")
    print(f"  总记录数: {total_records}")
    print(f"  无法访问: {[r['topic_name'] for r in results if not r['is_valid_json'] and not r['is_waf_or_captcha']]}")
    print(f"  被拦截: {[r['topic_name'] for r in results if r['is_waf_or_captcha']]}")


if __name__ == "__main__":
    main()
