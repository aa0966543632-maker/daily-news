# -*- coding: utf-8 -*-
"""每日時事更新腳本。

流程：
  1. 從 sources.py 的 RSS 來源抓取最新新聞
  2. 依「分類 × 地區」分桶、去重、取最新 N 則
  3. 呼叫 Groq API 產生繁體中文摘要與一句 insight
  4. 寫出 data/latest.json 與 data/YYYY-MM-DD.json（台灣日期）

環境變數：
  GROQ_API_KEY  必填，從 console.groq.com 取得
  GROQ_MODEL    選填，預設 llama-3.3-70b-versatile
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
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
BATCH_SIZE = int(os.environ.get("GROQ_BATCH_SIZE", "6"))  # 每次請求處理幾篇
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
def build_batch_prompt(batch) -> str:
    """一次處理多篇：要求模型回傳 JSON 陣列。"""
    lines = [
        "你是一位專業的財經與科技新聞編輯。以下有多則新聞，請為「每一則」產生繁體中文的摘要與洞察。",
        "規則：",
        "1. summary：2-3 句中立、精簡的繁體中文摘要（英文新聞也務必翻譯成繁體中文）。",
        "2. insight：一句話的洞察，點出『對讀者/市場的影響』或『為何值得關注』，避免空泛廢話。",
        "3. 只輸出 JSON 陣列，格式為 "
        '[{"id": <編號>, "summary": "...", "insight": "..."}, ...]，'
        "務必涵蓋所有編號，不要輸出任何其他文字或 markdown。",
        "",
        "新聞列表：",
    ]
    for n, item in enumerate(batch):
        cat = CATEGORY_LABEL.get(item["category"], item["category"])
        reg = REGION_LABEL.get(item["region"], item["region"])
        lines.append(
            f"[{n}] 分類:{cat}/{reg}｜標題:{item['title']}｜原文:{item['raw'] or '（無）'}"
        )
    return "\n".join(lines)


def parse_json_array(text: str):
    """從模型回覆中抽出 JSON 陣列。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON array found")
    return json.loads(match.group(0))


def enrich_with_groq(items):
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: 環境變數 GROQ_API_KEY 未設定", file=sys.stderr)
        sys.exit(1)

    client = Groq(api_key=api_key)

    # 先填 fallback，確保即使某批失敗每篇仍有摘要
    for item in items:
        item["summary"] = (item.get("raw") or item["title"])[:160]
        item["insight"] = ""

    batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    for bi, batch in enumerate(batches, 1):
        print(f"[groq 批次 {bi}/{len(batches)}] {len(batch)} 篇 … ", end="", flush=True)
        for attempt in range(4):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": build_batch_prompt(batch)}],
                    temperature=0.3,
                    max_tokens=2048,
                )
                text = resp.choices[0].message.content
                arr = parse_json_array(text)
                # 以 id 對應（容忍字串 id）；缺 id 時退而用「順序」對應
                by_id = {}
                for x in arr:
                    if isinstance(x, dict) and "id" in x:
                        try:
                            by_id[int(str(x["id"]).strip())] = x
                        except (ValueError, TypeError):
                            pass
                filled = 0
                for n, item in enumerate(batch):
                    data = by_id.get(n)
                    if data is None and n < len(arr) and isinstance(arr[n], dict):
                        data = arr[n]
                    if not isinstance(data, dict):
                        continue
                    summary = clean_text(data.get("summary", ""))
                    insight = clean_text(data.get("insight", ""))
                    if summary:
                        item["summary"] = summary
                    if insight:
                        item["insight"] = insight
                        filled += 1
                if filled == 0:
                    snippet = (text or "").strip().replace("\n", " ")[:200]
                    print(f"\n  ⚠ 未解析出 insight，回應片段：{snippet!r}")
                print(f"ok（{filled}/{len(batch)} 則有 insight）")
                break
            except Exception as exc:  # noqa: BLE001 - 重試後仍失敗則保留 fallback
                if attempt == 3:
                    print(f"fallback ({exc})")
                else:
                    time.sleep(5 * (attempt + 1))  # 5/10/15s backoff
        time.sleep(2)  # 批次間稍作間隔

    for item in items:
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
    items = enrich_with_groq(items)
    write_output(items)
    print(f"完成，共 {len(items)} 則。")


if __name__ == "__main__":
    main()
