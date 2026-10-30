"""News headline fetch + transparent keyword sentiment. No API key, no card.
Scores are simple lexicon counts - shown in the UI as raw headlines + score, nothing hidden."""
import urllib.request, xml.etree.ElementTree as ET, time

POS = {"surge","soar","beat","beats","profit","growth","record","upgrade","gain","gains","rally","wins","strong","boost","expands","partnership","dividend","outperform","jump","jumps","rise","rises","high","approval","order","deal"}
NEG = {"fall","falls","fell","crash","plunge","plunges","loss","losses","downgrade","miss","misses","weak","fraud","probe","fine","penalty","lawsuit","resigns","cuts","layoffs","debt","default","slump","drop","drops","warning","ban","recall","decline"}

def fetch_news(symbol_name, max_items=8):
    q = symbol_name.replace(" ", "%20") + "%20stock"
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=10).read())
        items = []
        for it in root.iter("item"):
            t = it.findtext("title") or ""
            items.append(t)
            if len(items) >= max_items:
                break
        return items
    except Exception:
        return []

def score_headlines(headlines):
    score, hits = 0, []
    for h in headlines:
        words = {w.strip(".,:;!?'\"()").lower() for w in h.split()}
        p, n = len(words & POS), len(words & NEG)
        score += p - n
        if p or n:
            hits.append((h, p - n))
    return score, hits

NAME_MAP = {"RELIANCE.NS": "Reliance Industries", "TCS.NS": "Tata Consultancy Services",
            "INFY.NS": "Infosys", "HDFCBANK.NS": "HDFC Bank", "ICICIBANK.NS": "ICICI Bank"}

class NewsDesk:
    """Fetch once per run; cache with timestamp so the journal can cite a real snapshot time."""
    def __init__(self):
        self.fetched_at, self.cache = None, {}
    def refresh(self, symbols):
        self.fetched_at = time.strftime("%Y-%m-%d %H:%M:%S")
        for s in symbols:
            heads = fetch_news(NAME_MAP.get(s, s))
            sc, hits = score_headlines(heads)
            self.cache[s] = {"headlines": heads, "score": sc, "hits": hits}
    def sentiment(self, symbol):
        return self.cache.get(symbol, {"headlines": [], "score": 0, "hits": []})
