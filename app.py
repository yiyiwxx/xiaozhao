"""
Flask Web 应用 - 校招进度聚合器界面
"""

import os
import json
from flask import Flask, render_template, request, jsonify
from crawler.config import CRAWL_CONFIG
from crawler.database import Database
from crawler.aggregator import Aggregator
from crawler.pipeline import Pipeline

app = Flask(__name__)
db = Database(CRAWL_CONFIG["db_path"])
agg = Aggregator(db)


@app.route("/")
def index():
    stats = db.get_stats()
    companies = db.get_all_companies()
    timelines = agg.all_company_timelines()

    return render_template(
        "index.html",
        stats=stats,
        companies=companies,
        timelines=timelines,
    )


@app.route("/company/<company_name>")
def company_detail(company_name: str):
    timeline = agg.company_timeline(company_name)
    return render_template("company.html", timeline=timeline)


@app.route("/api/timelines")
def api_timelines():
    return jsonify(agg.all_company_timelines())


@app.route("/api/company/<company_name>")
def api_company(company_name: str):
    return jsonify(agg.company_timeline(company_name))


@app.route("/api/stats")
def api_stats():
    return jsonify(db.get_stats())


@app.route("/api/events/role/<role_category>")
def api_events_by_role(role_category: str):
    return jsonify(agg.filter_by_role(role_category))


@app.route("/api/events/low-confidence")
def api_low_confidence():
    threshold = request.args.get("threshold", 0.5, type=float)
    return jsonify(agg.low_confidence_events(threshold))


@app.route("/crawl", methods=["POST"])
def trigger_crawl():
    """手动触发增量抓取"""
    max_pages = request.json.get("max_pages", 2) if request.is_json else 2
    pipeline = Pipeline()
    try:
        fetch_stats = pipeline.run_fetch(max_pages=max_pages)
        parse_stats = pipeline.run_parse()
        return jsonify({
            "status": "ok",
            "fetch": fetch_stats,
            "parse": parse_stats,
        })
    finally:
        pipeline.close()


@app.route("/export")
def export_data():
    output = os.path.join("data", "export.json")
    path = agg.export_json(output)
    return jsonify({"path": path, "message": "导出成功"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
