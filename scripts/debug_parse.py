"""诊断：为什么事件提取全部为0"""
import sys, os, json, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.parsers import extract_events

conn = sqlite3.connect('data/nowcoder.db')
cur = conn.cursor()
cur.execute("SELECT title, content, detail_url, show_time, raw_json, content_id FROM raw_records LIMIT 3")
rows = cur.fetchall()

for row in rows:
    raw = json.loads(row[4])
    ub = raw.get("userBrief") or {}
    try:
        events = extract_events(
            title=row[0] or "",
            content=row[1] or "",
            topic_uuid="test",
            content_id=row[5],
            publish_time_ms=row[3] or 0,
            detail_url=row[2] or "",
            author_id=str(raw.get("creator", "") or ub.get("userId", "")),
        )
        print(f"CID={row[5]}: events={len(events)}")
        for e in events[:2]:
            print(f"  {e['company']} | {e['event_type']} | detail={e['detail_url'][:60]}")
    except Exception as ex:
        print(f"CID={row[5]}: ERROR {ex}")

conn.close()
