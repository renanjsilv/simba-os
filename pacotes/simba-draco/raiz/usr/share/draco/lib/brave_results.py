"""Turn a Brave Search results page (stdin) into short plain-text results."""
import html
import re
import sys


def clean(fragment):
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment or ""))
    return re.sub(r"\s+", " ", text).strip()


page = sys.stdin.read()
results = []
for block in page.split('data-type="web"')[1:]:
    url = re.search(r'<a href="(https?://[^"]+)"', block)
    title = re.search(r'search-snippet-title[^"]*"[^>]*title="([^"]*)"', block)
    desc = re.search(r'<div class="content [^"]*"[^>]*>(.*?)</div>', block, re.S)
    if not url:
        continue
    results.append(f"- {clean(title.group(1) if title else '')}\n  {url.group(1)}\n  {clean(desc.group(1) if desc else '')[:300]}")
    if len(results) >= 6:
        break

print("\n".join(results) if results else "sem resultados (tente a ferramenta WebSearch)")
