#!/usr/bin/env python3
"""Maharashtra 24/7 – fetches Marathi news/video feeds and writes news.json.
Only headline + short snippet + link to the original are stored (no full articles)."""
import json, os, re, sys, time, html, hashlib
from datetime import datetime, timezone, timedelta
from string import Template
from urllib.parse import quote
from pathlib import Path
import socket, urllib.request, feedparser
from urllib.parse import urljoin, urlparse
socket.setdefaulttimeout(20)
feedparser.USER_AGENT = 'Mozilla/5.0 (compatible; Maharashtra247Bot/1.0)'

ROOT = Path(__file__).parent
MAX_ITEMS, SNIPPET, KEEP_DAYS = 600, 200, 14
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

PAGE = Template("""<!DOCTYPE html><html lang="mr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>$title – महाराष्ट्र 24/7</title><link rel="icon" href="../favicon.png"><meta name="description" content="$desc">
<meta property="og:title" content="$title"><meta property="og:description" content="$desc"><meta property="og:type" content="article">$ogimg
<link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;800&display=swap" rel="stylesheet">
<style>:root{--bg:#f4f2ec;--card:#fff;--tx:#1b1b1f;--mu:#6b6b73;--br:#e6e2d8}@media(prefers-color-scheme:dark){:root{--bg:#0f1116;--card:#1a1d25;--tx:#f0eee8;--mu:#9a9aa5;--br:#2a2e39;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:18px/1.75 'Mukta',system-ui,sans-serif}
header{background:linear-gradient(120deg,#0b1f4d,#1d4a9c);padding:10px 16px}header a{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;font-weight:800;font-size:24px;max-width:760px;margin:0 auto}
header img{width:46px;height:46px;border-radius:50%;box-shadow:0 0 0 2px #ffc83d}header b{color:#ffc83d}
main{max-width:760px;margin:0 auto;padding:16px}.tag{background:#e8680c;color:#fff;border-radius:6px;padding:1px 10px;font-size:14px}
h1{font-size:30px;line-height:1.35;margin:10px 0}.meta{color:var(--mu);font-size:15px;margin-bottom:14px}
img.p{width:100%;border-radius:12px;margin:10px 0;display:block}p{margin:0 0 16px}iframe{width:100%;aspect-ratio:16/9;border:0;border-radius:12px;margin:10px 0}
.sh{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0}.sh a{background:#25d366;color:#fff;padding:10px 18px;border-radius:22px;text-decoration:none;font-weight:700}.sh a.b{background:#12306b}
footer{background:#0b1f4d;color:#cfd8f5;text-align:center;padding:20px 16px;font-size:14px}footer a{color:#ffc83d}</style></head><body>
<header><a href="../"><img src="../logo.png" alt="">महाराष्ट्र <b>24/7</b></a></header>
<main><span class="tag">$cat</span><h1>$title</h1><div class="meta">$source · $when</div>$cover$yt$body$photos
<div class="sh"><a href="https://wa.me/?text=$wa" target="_blank" rel="noopener">💬 WhatsApp वर शेअर करा</a><a class="b" href="../">← सर्व बातम्या</a></div></main>
<footer><b>महाराष्ट्र 24/7</b> ™ · संपादक: श्री. जयंत बडवाईक · <a href="tel:+919850302488">+91 98503 02488</a> · <a href="mailto:jayantbadwaik30@gmail.com">ईमेल</a></footer></body></html>""")

def site_base():
    r = os.environ.get("GITHUB_REPOSITORY", "")
    return f"https://{r.split('/')[0].lower()}.github.io/{r.split('/')[1]}/" if "/" in r else ""

def build_pages(manual):
    """One static, shareable page per own story (good for WhatsApp previews and Google)."""
    from urllib.parse import quote as q
    out = ROOT / "a"; base = site_base(); ids = set()
    rel = lambda p: p if p.startswith("http") else "../" + p
    ab = lambda p: p if p.startswith("http") else base + p
    ist = timezone(timedelta(hours=5, minutes=30))
    for m in manual:
        if not m.get("own") or not m.get("body") or not re.fullmatch(r"[\w-]+", str(m.get("id", ""))): continue
        out.mkdir(exist_ok=True); ids.add(m["id"])
        e = html.escape
        body = "".join(f"<p>{e(p)}</p>" for p in re.split(r"\n+", m["body"]) if p.strip())
        cover = f'<img class="p" src="{e(rel(m["img"]))}" alt="">' if m.get("img") and not m.get("yt") else ""
        yt = f'<iframe src="https://www.youtube-nocookie.com/embed/{e(m["yt"])}" allowfullscreen></iframe>' if m.get("yt") else ""
        photos = "".join(f'<img class="p" src="{e(rel(p))}" alt="" loading="lazy">' for p in m.get("photos", []))
        url = (base + "a/" + m["id"] + ".html") if base else ""
        og = f'<meta property="og:image" content="{e(ab(m["img"]))}">' if m.get("img") and (base or m["img"].startswith("http")) else ""
        when = datetime.fromtimestamp(m["ts"] / 1000, ist).strftime("%d-%m-%Y, %I:%M %p")
        (out / (m["id"] + ".html")).write_text(PAGE.substitute(
            title=e(m["title"]), desc=e(m.get("summary", "")[:160]), ogimg=og, cat=e(m.get("cat", "")),
            source=e(m.get("source", "")), when=when, cover=cover, yt=yt, body=body, photos=photos,
            wa=q(m["title"] + " " + url)), encoding="utf-8")
    if out.exists():
        for f in out.glob("*.html"):
            if f.stem not in ids: f.unlink()  # story was deleted

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
    mp = ROOT / "manual.json"  # your own stories (written in admin.html)
    manual = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else []
    build_pages(manual)
    for m in manual:  # keep news.json light: full text lives only in the story page
        items.append({k: v for k, v in m.items() if k not in ("body", "photos")})
    # keep older stories from earlier runs (so the list grows and "load more" has content)
    pj = ROOT / "news.json"
    if pj.exists():
        try:
            have = {i["id"] for i in items} | {re.sub(r"\W+", "", i["title"].lower())[:80] for i in items}
            cutoff = (time.time() - KEEP_DAYS * 86400) * 1000
            for old in json.loads(pj.read_text(encoding="utf-8"))["items"]:
                k = re.sub(r"\W+", "", old["title"].lower())[:80]
                if old["id"].startswith("m") or old["ts"] < cutoff or old["id"] in have or k in have: continue
                items.append(old); have.add(old["id"]); have.add(k)
        except Exception as ex: print("WARN could not merge old news:", ex)
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
