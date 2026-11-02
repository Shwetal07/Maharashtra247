#!/usr/bin/env python3
"""Maharashtra 24/7 – fetches Marathi news/video feeds and writes news.json.
Only headline + short snippet + link to the original are stored (no full articles)."""
import json, re, sys, time, html, hashlib
from urllib.parse import quote
from pathlib import Path
import socket, urllib.request, feedparser
from urllib.parse import urljoin, urlparse
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

def og_image(url):
    """Read the public preview image (og:image) of an article page, like link previews do."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Maharashtra247Bot/1.0)"})
        with urllib.request.urlopen(req, timeout=8) as r:
            page = r.read(200000).decode("utf-8", "ignore")
        for pat in (r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']'):
            m = re.search(pat, page, re.I)
            if m: return urljoin(url, html.unescape(m.group(1)))
    except Exception:
        pass
    return ""

def fill_images(items, limit=40):
    prev = {}
    p = ROOT / "news.json"
    if p.exists():
        try: prev = {i["id"]: i for i in json.loads(p.read_text(encoding="utf-8"))["items"]}
        except Exception: pass
    tried = 0
    for it in items:
        if it["img"]: continue
        old = prev.get(it["id"])
        if old is not None:               # seen before: reuse result, do not retry
            it["img"] = old.get("img", ""); continue
        if tried >= limit or "news.google.com" in urlparse(it["link"]).netloc: continue
        tried += 1; it["img"] = og_image(it["link"])

def load_feeds():
    feeds = json.loads((ROOT / "feeds.json").read_text(encoding="utf-8"))["feeds"]
    for f in feeds:  # "gnews": "town name" -> Google News Marathi search feed
        if f.get("gnews"):
            f["url"] = "https://news.google.com/rss/search?q=" + quote(f["gnews"] + " when:7d") + "&hl=mr&gl=IN&ceid=IN:mr"
            f["type"] = "news"; f.setdefault("force", True); f.setdefault("cat", f["gnews"]); f.setdefault("name", "Google News – " + f["gnews"])
        else:
            f["url"] = quote(f["url"], safe=":/?&=%+@")
    return feeds

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
                  "cat": f["cat"] if f.get("force") else categorize(title, f["cat"]), "source": src, "link": link,
                  "img": image_of(e), "ts": ts_of(e)}
            if f["type"] == "video" and e.get("yt_videoid"): it["yt"] = e["yt_videoid"]; it["img"] = it["img"] or f"https://i.ytimg.com/vi/{e['yt_videoid']}/hqdefault.jpg"
            items.append(it)
    mp = ROOT / "manual.json"  # your own stories, same fields as above
    if mp.exists(): items += json.loads(mp.read_text(encoding="utf-8"))
    items.sort(key=lambda x: x["ts"], reverse=True)
    fill_images(items[:MAX_ITEMS])
    forced = {f["cat"] for f in load_feeds() if f.get("force")}
    keep = items[:MAX_ITEMS]; ids = {i["id"] for i in keep}; cnt = {}
    for it in items:  # make sure each local town keeps up to 40 stories
        if it["cat"] in forced:
            cnt[it["cat"]] = cnt.get(it["cat"], 0) + 1
            if it["id"] not in ids and cnt[it["cat"]] <= 40: keep.append(it)
    items = sorted(keep, key=lambda x: x["ts"], reverse=True)
    (ROOT / "news.json").write_text(json.dumps({"updated": int(time.time() * 1000), "items": items}, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(items)} items")

if __name__ == "__main__":
    check() if "--check" in sys.argv else run()
