// PIPEDREAM STEP 1 — "fetch_filter"  (Node.js code step) — NO data store needed.
// Pulls the RSS feeds, keyword-gates them, and de-dupes against what's ALREADY on the
// Calendar page (the page itself is our memory). Returns fresh candidates + recent headlines.
import Parser from "rss-parser";

const CAL_ID = 447; // the Calendar page = our memory

export default defineComponent({
  async run({ steps, $ }) {
    const parser = new Parser({ timeout: 10000 });
    const FEEDS = [
      "https://www.forexlive.com/feed/news",
      "https://www.fxstreet.com/rss/news",
      "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/",
      "https://www.investing.com/rss/news_25.rss",
      "https://www.investing.com/rss/news_11.rss"
    ];
    const KW = /(fed|fomc|rate cut|rate hike|interest rate|cpi|ppi|pce|inflation|jobs report|nfp|payroll|gdp|ism|retail sales|treasury|yield|dollar|oil|crude|eia|opec|gold|silver|copper|natural gas|s&p|nasdaq|dow|russell|index futures|futures|cme|cftc|nfa|bitcoin|prop firm|ninjatrader|tradovate|rithmic|apex|topstep|corn|wheat|soybean|soymeal|soyoil|grain|crop|usda|wasde|harvest|acreage|coffee|sugar|cotton|cocoa|cattle|hog|livestock|ethanol|agricultur)/i;

    // 1) pull each feed into its OWN list (so one high-volume feed can't crowd the others out)
    const perFeed = [];
    for (const url of FEEDS) {
      const arr = [];
      try {
        const f = await parser.parseURL(url);
        for (const it of (f.items || []).slice(0, 25)) {
          const text = `${it.title || ""} ${it.contentSnippet || it.content || ""}`;
          if (!KW.test(text)) continue;
          const link = it.link || it.guid || "";
          const pub = it.isoDate || it.pubDate || "";
          const pts = pub ? new Date(pub).getTime() : NaN;
          if (!isNaN(pts) && (Date.now() - pts) > 3 * 24 * 60 * 60 * 1000) continue; // drop stale
          arr.push({ title: (it.title || "").trim(), source: f.title || url, link, published: pub, snippet: (it.contentSnippet || "").slice(0, 280) });
        }
      } catch (e) { console.warn(`feed failed [${url}]: ${e.message}`); }
      perFeed.push(arr);
    }
    // round-robin merge: item 0 of each feed, then item 1 of each, ... so every feed gets a fair seat
    let candidates = [];
    const maxLen = Math.max(0, ...perFeed.map(a => a.length));
    for (let i = 0; i < maxLen; i++) for (const arr of perFeed) if (arr[i]) candidates.push(arr[i]);

    // 2) read the Calendar page = our memory (links we've posted + recent headlines)
    const BASE = process.env.WP_BASE;
    const AUTH = "Basic " + Buffer.from(`${process.env.WP_USER}:${process.env.WP_APP_PASS}`).toString("base64");
    const seenLinks = new Set();
    const recentHeadlines = [];
    try {
      const r = await fetch(`${BASE}/wp-json/wp/v2/pages/${CAL_ID}?context=edit`, { headers: { Authorization: AUTH } });
      const pg = await r.json();
      const html = (pg.content && pg.content.raw) || "";
      for (const m of html.matchAll(/data-link="([^"]+)"/g)) seenLinks.add(m[1]);
      for (const m of html.matchAll(/line-height:1\.4;">([^<]+?) &mdash;/g)) recentHeadlines.push(m[1].trim());
    } catch (e) { /* if the read fails, we just won't dedupe this run */ }

    const fresh = candidates.filter(c => c.link && !seenLinks.has(c.link)).slice(0, 25);
    if (!fresh.length) return $.flow.exit("no fresh items this run");
    return { candidates: fresh, recent: recentHeadlines.slice(0, 25) };
  }
});
