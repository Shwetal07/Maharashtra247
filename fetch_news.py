#!/usr/bin/env python3
"""Maharashtra 24/7 – fetches Marathi news/video feeds and writes news.json.
Only headline + short snippet + link to the original are stored (no full articles)."""
import json, re, sys, time, html, hashlib
from pathlib import Path
import socket, feedparser
socket.setdefaulttimeout(20)
feedparser.USER_AGENT = 'Mozilla/5.0 (compatible; Maharashtra247Bot/1.0)'

ROOT = Path(__file__).parent
MAX_ITEMS, SNIPPET = 300, 200
KEYWORDS = {  # first match wins, order matters
 "क्रीडा": ["क्रिकेट", "सामना", "आयपीएल", "खेळाडू", "फुटबॉल", "ऑलिम्पिक", "कबड्डी"],
 "मनोरंजन": ["चित्रपट", "अभिनेत", "अभिनेत्री", "बॉलिवूड", "मालिका", "सिनेमा"],
 "क्राईम": ["अटक", "हत्या", "गुन्हा", "पोलीस", "चोरी", "अपघात", "फसवणूक"],
 "राजकारण": ["मुख्यमंत्री", "भाजप", "काँग्रेस", "शिवसेना", "राष्ट्रवादी", "निवडणूक", "आमदार", "खासदार", "मंत्री"],
 "व्यवसाय": ["शेअर", "सेन्सेक्स", "निफ्टी", "सोने", "बाजार", "अर्थसंकल्प", "रुपया"],
 "नाशिक": ["नाशिक"], "पुणे": ["पुणे", "पिंपरी"], "नागपूर": ["नागपूर"], "मुंबई": ["मुंबई", "ठाणे"],
}
def clean(t):
    t = re.sub(r"<[^>]+>", " ", html.unescape(t or ""))
    return re.sub(r"\s+", " ", t).strip()
def categorize(title, default):
    for cat, words in KEYWORDS.items():
        if any(w in title for w in words): return cat
    return default
def image_of(e):
    for k in ("media_thumbnail", "media_content"):
        v = e.get(k)
        if v and v[0].get("url"): return v[0]["url"]
    for l in e.get("links", []):
        if l.get("type", "").startswith("image"): return l.get("href", "")
    m = re.search(r'<img[^>]+src="([^"]+)"', e.get("summary", "") or "")
    return m.group(1) if m else ""
def ts_of(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return int(time.mktime(t) * 1000) if t else int(time.time() * 1000)

def load_feeds():
    return json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))["feeds"]

def check():
    for f in load_feeds():
        d = feedparser.parse(f["url"])
        ok = len(d.entries) > 0
        print(("OK   " if ok else "FAIL ") + f"{f['name']}: {len(d.entries)} items" + ("" if ok else f"  ({d.get('bozo_exception', 'empty')})"))

def run():
    items, seen = [], set()
    for f in load_feeds():
        if not f.get("enabled", True): continue
        try: d = feedparser.parse(f["url"])
        except Exception as ex: print("WARN failed:", f["name"], ex); continue
        if not d.entries: print("WARN no items:", f["name"]); continue
        for e in d.entries:
            title, link = clean(e.get("title")), e.get("link", "")
            if not title or not link: continue
            key = re.sub(r"\W+", "", title.lower())[:80]
            if key in seen or link in seen: continue
            seen.update([key, link])
            src = clean(getattr(e.get("source"), "title", "")) if e.get("source") else f["name"].split(" (")[0]
            it = {"id": hashlib.md5(link.encode()).hexdigest()[:12], "title": title,
                  "summary": clean(e.get("summary"))[:SNIPPET] if f["type"] == "news" and clean(e.get("summary")) != title else "",
                  "cat": categorize(title, f["cat"]), "source": src, "link": link,
                  "img": image_of(e), "ts": ts_of(e)}
            if f["type"] == "video" and e.get("yt_videoid"): it["yt"] = e["yt_videoid"]; it["img"] = it["img"] or f"https://i.ytimg.com/vi/{e['yt_videoid']}/hqdefault.jpg"
            items.append(it)
    mp = ROOT / "manual.json"  # your own stories, same fields as above
    if mp.exists(): items += json.loads(mp.read_text(encoding="utf-8"))
    items.sort(key=lambda x: x["ts"], reverse=True)
    (ROOT / "news.json").write_text(json.dumps({"updated": int(time.time() * 1000), "items": items[:MAX_ITEMS]}, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {min(len(items), MAX_ITEMS)} items")

if __name__ == "__main__":
    check() if "--check" in sys.argv else run()
