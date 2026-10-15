#!/usr/bin/env python3
"""Refresh the homepage plan tiles from Gumroad.

For every tile in public/index.html marked with data-gumroad="<product slug>",
this pulls the product's public Gumroad page and updates:
  - the tile image  (<img data-gumroad-thumb="slug">)  -> Gumroad thumbnail, saved to public/images/
  - the proof line  (<p class="proof" data-gumroad="slug">)  -> stars, review count, sales count

No login or API key: it reads the same public page any visitor sees.
Hand-written parts of a tile (name, one-line description, alt text) are never touched.

Run:  python3 scripts/sync_gumroad.py
Exit code 1 if any product could not be read. Products that were read are still updated,
and a tile that fails keeps its last good values.
"""
import glob
import hashlib
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "public", "index.html")
IMAGES = os.path.join(ROOT, "public", "images")
STORE = "https://byos.gumroad.com/l/"
UA = "Mozilla/5.0 (compatible; byosdesign-sync/1.0; +https://byosdesign.com)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def product_data(slug):
    """Return {thumbnail_url, reviews, average, sales} from the public product page."""
    page = get(STORE + slug).decode("utf-8", "replace")
    out = {}
    m = re.search(r'data-page="([^"]+)"', page)
    if m:
        p = json.loads(html.unescape(m.group(1)))["props"]["product"]
        r = p.get("ratings") or {}
        out = {
            "thumbnail_url": p.get("thumbnail_url"),
            "reviews": r.get("count"),
            "average": r.get("average"),
            "sales": p.get("sales_count"),  # None when "show sales count" is off in Gumroad
        }
    # Fallback for ratings: schema.org data Gumroad publishes for search engines
    if out.get("reviews") is None:
        for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
            try:
                agg = json.loads(block).get("aggregateRating") or {}
            except ValueError:
                continue
            if agg:
                out["reviews"], out["average"] = agg.get("reviewCount"), agg.get("ratingValue")
    if out.get("reviews") is None and not out.get("thumbnail_url"):
        raise ValueError("no product data found on the page")
    return out


def proof_html(d):
    parts = []
    n, avg = d.get("reviews") or 0, d.get("average") or 0
    if n:
        filled = max(0, min(5, int(float(avg) + 0.5)))
        stars = "&#9733;" * filled + ('<span class="off">' + "&#9733;" * (5 - filled) + "</span>" if filled < 5 else "")
        parts.append(f'<span class="stars" aria-label="Rated {float(avg):.1f} out of 5">{stars}</span>'
                     f'{n} review{"" if n == 1 else "s"}')
    if d.get("sales"):
        parts.append(f'{d["sales"]} sold')
    return (" &middot; ".join(parts) + " on Gumroad") if parts else ""


def image_ext(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    if b[:4] == b"GIF8":
        return "gif"
    raise ValueError("thumbnail is not a png, jpg, webp or gif")


def sync_thumb(t, slug, url):
    data = get(url)
    ext = image_ext(data)
    name = f"{slug}-thumb.{ext}"
    path = os.path.join(IMAGES, name)
    old = open(path, "rb").read() if os.path.exists(path) else None
    if old != data:
        open(path, "wb").write(data)
    for other in glob.glob(os.path.join(IMAGES, f"{slug}-thumb.*")):
        if os.path.basename(other) != name:
            os.remove(other)
    src = f"/images/{name}?v={hashlib.sha1(data).hexdigest()[:8]}"
    pat = re.compile(r'(<img\b[^>]*\bdata-gumroad-thumb="' + re.escape(slug) + r'"[^>]*>)')

    def swap(m):
        return re.sub(r'\bsrc="[^"]*"', f'src="{src}"', m.group(1))

    return pat.sub(swap, t)


def sync_proof(t, slug, d):
    pat = re.compile(r'(<p class="proof" data-gumroad="' + re.escape(slug) + r'")(?: hidden)?>(.*?)</p>', re.S)
    body = proof_html(d)
    return pat.sub(lambda m: f'{m.group(1)}{"" if body else " hidden"}>{body}</p>', t)


def main():
    t = open(INDEX, encoding="utf-8").read()
    slugs = sorted(set(re.findall(r'data-gumroad(?:-thumb)?="([A-Za-z0-9_-]+)"', t)))
    failed = []
    for slug in slugs:
        try:
            d = product_data(slug)
            if d.get("thumbnail_url"):
                t = sync_thumb(t, slug, d["thumbnail_url"])
            t = sync_proof(t, slug, d)
            print(f"{slug}: {d.get('reviews')} reviews, avg {d.get('average')}, {d.get('sales')} sold")
        except Exception as e:  # keep last good values for this tile
            failed.append(slug)
            print(f"{slug}: FAILED, kept last values ({e})", file=sys.stderr)
    if t != open(INDEX, encoding="utf-8").read():
        open(INDEX, "w", encoding="utf-8").write(t)
        print("index.html updated")
    else:
        print("index.html unchanged")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
