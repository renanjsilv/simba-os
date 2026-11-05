"""Turn a YouTube results page (stdin) into lines: id | title | channel | duration | published | views."""
import json
import re
import sys


def text(node):
    node = node or {}
    return node.get("simpleText") or "".join(r.get("text", "") for r in node.get("runs", []))


def videos(obj):
    if isinstance(obj, dict):
        if "videoRenderer" in obj:
            yield obj["videoRenderer"]
        for v in obj.values():
            yield from videos(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from videos(v)


limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
page = sys.stdin.read()
m = re.search(r"var ytInitialData = (\{.*?\});</script>", page)
rows = []
if m:
    for v in videos(json.loads(m.group(1))):
        if not v.get("lengthText"):  # live streams/upcoming: no duration
            continue
        rows.append(" | ".join([v["videoId"], text(v.get("title")), text(v.get("ownerText")),
                                text(v.get("lengthText")), text(v.get("publishedTimeText")),
                                text(v.get("viewCountText"))]))
        if len(rows) >= limit:
            break
print("\n".join(rows) if rows else "sem resultados")
