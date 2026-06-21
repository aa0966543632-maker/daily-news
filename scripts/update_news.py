# -*- coding: utf-8 -*-
"""每日時事更新腳本。

流程：
  1. 從 sources.py 的 RSS 來源抓取最新新聞
  2. 依「分類 × 地區」分桶、去重、取最新 N 則
  3. 呼叫 Gemini API 產生繁體中文摘要與一句 insight
  4. 寫出 data/latest.json 與 data/YYYY-MM-DD.json（台灣日期）

環境變數：
  GEMINI_API_KEY  必填，從 Google AI Studio 取得
  GEMINI_MODEL    選填，預設 gemini-2.5-flash
"""

import hashlib
import html
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser

from sources import FEEDS, MAX_PER_BUCKET

# ───────────────────────── 設定 ─────────────────────────
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
TAIPEI = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

CATEGORY_LABEL = {"finance": "金融", "ai": "AI科技", "investment": "投資"}
REGION_LABEL = {"taiwan": "台灣", "international": "國際"}


def clean_text(raw: str) -> str:
    """移除 HTML 標籤、解碼 entity、壓縮空白。"""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def entry_time(entry) -> datetime:
    """取得發布時間（UTC）；無法解析時回傳 epoch 0。"""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def fetch_entries():
    """抓取所有 feed，依 (category, region) 分桶並取最新 MAX_PER_BUCKET 則。"""
    buckets = defaultdict(list)
    seen = set()

    for feed in FEEDS:
        print(f"[fetch] {feed['name']} … ", end="", flush=True)
        try:
            parsed = feedparser.parse(feed["url"])
        except Exception as exc:  # noqa: BLE001 - 單一 feed 失敗不應中斷整批
            print(f"FAILED ({exc})")
            continue
        if parsed.bozo and not parsed.entries:
            print("FAILED (no entries)")
            continue

        count = 0
        for entry in parsed.entries:
            url = entry.get("link")
            title = clean_text(entry.get("title", ""))
            if not url or not title:
                continue
            uid = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
            if uid in seen:
                continue
            seen.add(uid)

            buckets[(feed["category"], feed["region"])].append({
                "id": uid,
                "title": title,
                "source": feed["name"],
                "url": url,
                "category": feed["category"],
                "region": feed["region"],
                "published": entry_time(entry).isoformat(),
                "raw": clean_text(entry.get("summary", entry.get("description", "")))[:600],
            })
            count += 1
        print(f"{count} entries")

    items = []
    for key, lst in buckets.items():
        lst.sort(key=lambda x: x["published"], reverse=True)
        items.extend(lst[:MAX_PER_BUCKET])
    return items


# ───────────────────────── Gemini ─────────────────────────
def build_prompt(item) -> str:
    return (
        "你是一位專業的財經與科技新聞編輯。請根據以下新聞，產生繁體中文的摘要與洞察。\n"
        "規則：\n"
        "1. summary：2-3 句中立、精簡的繁體中文摘要。\n"
        "2. insight：一句話的洞察，點出『這對讀者/市場的影響』或『為何值得關注』，"
        "避免空泛廢話。\n"
        "3. 只輸出 JSON，格式為 {\"summary\": \"...\", \"insight\": \"...\"}，不要加任何其他文字或 markdown。\n\n"
        f"分類：{CATEGORY_LABEL.get(item['category'], item['category'])} / "
        f"{REGION_LABEL.get(item['region'], item['region'])}\n"
        f"標題：{item['title']}\n"
        f"原文摘要：{item['raw'] or '（無）'}\n"
    )


def parse_json_response(text: str):
    """從模型回覆中抽出 JSON 物件。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found")
    return json.loads(match.group(0))


def enrich_with_gemini(items):
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: 環境變數 GEMINI_API_KEY 未設定", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    total = len(items)

    for i, item in enumerate(items, 1):
        print(f"[gemini {i}/{total}] {item['title'][:40]} … ", end="", flush=True)
        summary, insight = item["raw"][:160], ""
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=build_prompt(item),
                )
                data = parse_json_response(resp.text)
                summary = clean_text(data.get("summary", "")) or summary
                insight = clean_text(data.get("insight", ""))
                print("ok")
                break
            except Exception as exc:  # noqa: BLE001 - 重試後仍失敗則用 fallback
                if attempt == 2:
                    print(f"fallback ({exc})")
                else:
                    time.sleep(2 * (attempt + 1))
        item["summary"] = summary
        item["insight"] = insight
        item.pop("raw", None)

    return items


# ───────────────────────── 輸出 ─────────────────────────
def write_output(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TAIPEI)
    payload = {
        "updated_at": now.isoformat(),
        "count": len(items),
        "items": items,
    }
    latest = DATA_DIR / "latest.json"
    archive = DATA_DIR / f"{now:%Y-%m-%d}.json"
    for path in (latest, archive):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[write] {path.relative_to(ROOT)}")


def main():
    items = fetch_entries()
    if not items:
        print("沒有抓到任何新聞，結束。", file=sys.stderr)
        sys.exit(1)
    items.sort(key=lambda x: x["published"], reverse=True)
    items = enrich_with_gemini(items)
    write_output(items)
    print(f"完成，共 {len(items)} 則。")


if __name__ == "__main__":
    main()
