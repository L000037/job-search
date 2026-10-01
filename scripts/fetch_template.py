# -*- coding: utf-8 -*-
"""
通用招聘站点抓取骨架（job-search）
用法：
1. 通过 WebFetch / JS bundle 分析 / 浏览器 XHR 拦截拿到真实 API 端点与请求体；
2. 把本文件复制到 <workspace>/fetchers/<公司名>.py，改好下面配置段与 build_body/parse；
3. python <公司名>.py 全量翻页，结果写入 <workspace>/data/<公司名>_all_jobs.json。
"""
import json
import os
import time
import requests

# 复制到 <workspace>/fetchers/ 后，上两级即工作区根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

# === 按站点修改这一段 ===
API_URL = "https://example.com/api/v1/positions"
COMPANY = "example"                   # 公司英文小写名，决定输出文件名
METHOD = "POST"                       # GET / POST
DATA_TYPE = "json"                    # json / form
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://example.com/",
    "Origin": "https://example.com",
}
PAGE_SIZE = 20
OUT_PATH = os.path.join(DATA_DIR, f"{COMPANY}_all_jobs.json")
# ========================


def build_body(page: int) -> dict:
    """翻页参数：GET 时作为 query，POST 时按 DATA_TYPE 发送。"""
    return {"pageNum": page, "pageSize": PAGE_SIZE}


def parse(resp_json: dict):
    """返回 (岗位列表, 总数)，按站点实际结构调整。"""
    result = resp_json.get("result") or resp_json.get("data") or {}
    return result.get("list", []), result.get("total", 0)


def main():
    all_jobs, page = [], 1
    session = requests.Session()
    while True:
        body = build_body(page)
        if METHOD == "GET":
            r = session.get(API_URL, params=body, headers=HEADERS, timeout=20)
        elif DATA_TYPE == "form":
            r = session.post(API_URL, data=body, headers=HEADERS, timeout=20)
        else:
            r = session.post(API_URL, json=body, headers=HEADERS, timeout=20)
        data = r.json()
        jobs, total = parse(data)
        if not jobs:
            print("stop at page", page, "raw:", json.dumps(data, ensure_ascii=False)[:300])
            break
        all_jobs.extend(jobs)
        print(f"page {page}: +{len(jobs)} ({len(all_jobs)}/{total})")
        if total and len(all_jobs) >= total:
            break
        page += 1
        time.sleep(0.5)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)
    print("saved", len(all_jobs), "->", OUT_PATH)


def selftest():
    """无网络自检：校验参数构造与响应解析逻辑。"""
    body = build_body(1)
    assert "pageNum" in body and body["pageNum"] == 1
    jobs, total = parse({"result": {"list": [{"name": "demo"}], "total": 1}})
    assert jobs == [{"name": "demo"}] and total == 1
    print("selftest ok")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
