#!/usr/bin/env python3
"""Build gumroad/profile.html from profile.template.html + live Gumroad product data.

Usage:
  GUMROAD_ACCESS_TOKEN=... python3 gumroad/build_profile.py            # fetch products, write profile.html
  python3 gumroad/build_profile.py --products products.json            # use a saved API response

Every published product becomes a tile: thumbnail, name, price and link all come
from Gumroad, so editing a product in Gumroad and re-running this is the whole
update loop. Nothing is duplicated by hand.
"""
import argparse
import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.gumroad.com/v2/products"


def fetch_products(token):
    out = subprocess.run(
        ["curl", "-sS", "--fail", API, "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def tile(p):
    name = html.escape(p["name"])
    url = html.escape(p.get("short_url") or p.get("url"))
    img = p.get("thumbnail_url") or p.get("preview_url") or ""
    price = html.escape(p.get("formatted_price") or "")
    img_tag = f'<img src="{html.escape(img)}" alt="{name}" loading="lazy">' if img else ""
    return (
        f'      <a class="tile" href="{url}">\n'
        f'        {img_tag}\n'
        f'        <span class="name">{name}</span>\n'
        f'        <span class="by">BYOS plans</span>\n'
        f'        <span class="foot"><span>view plans &rarr;</span><span class="price">{price}</span></span>\n'
        f'      </a>'
    )


def build(data):
    products = [p for p in data.get("products", []) if p.get("published") and not p.get("deleted")]
    tiles = "\n".join(tile(p) for p in products)
    tpl = open(os.path.join(HERE, "profile.template.html"), encoding="utf-8").read()
    return tpl.replace("{{PRODUCT_TILES}}", tiles), len(products)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", help="saved /v2/products JSON instead of calling the API")
    ap.add_argument("--out", default=os.path.join(HERE, "profile.html"))
    a = ap.parse_args()
    if a.products:
        data = json.load(open(a.products))
    else:
        token = os.environ.get("GUMROAD_ACCESS_TOKEN")
        if not token:
            sys.exit("Set GUMROAD_ACCESS_TOKEN or pass --products")
        data = fetch_products(token)
    page, n = build(data)
    open(a.out, "w", encoding="utf-8").write(page)
    print(f"wrote {a.out} with {n} product tile(s)")


if __name__ == "__main__":
    main()
