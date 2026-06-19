// PIPEDREAM STEP 3 — "route_write"  (Node.js code step) — NO data store needed.
// Writes every kept item into the Calendar (447): the warehouse zone + the single hot story.
// Embeds data-link in each row so the page itself becomes the dedupe memory. Returns a Slack summary.
// Env vars: WP_BASE, WP_USER, WP_APP_PASS.
// To turn on the fan-out later, add more targets in routeTargets().

const ACCENTS = {
  hot:    { line: "#DC2626", bg: "#FEF2F2", fg: "#DC2626" },
  normal: { line: "#2563EB", bg: "#EEF3FE", fg: "#2563EB" },
  low:    { line: "#C9961A", bg: "#FBF3DC", fg: "#8A5F08" }
};

function pubTs(x) { const t = new Date(x && x.published ? x.published : 0).getTime(); return isNaN(t) ? 0 : t; }

// absolute, unambiguous timestamp in US Eastern (market) time, e.g. "Jun 4, 2:32 PM ET"
function stamp(published) {
  const d = published ? new Date(published) : null;
  if (!d || isNaN(d.getTime())) return "Latest";
  return d.toLocaleString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " ET";
}

// deep-link each story to the most relevant page ON YOUR SITE (SEO + keeps readers in-house)
const EVT_URL = { cpi:"/economic-events/cpi/", ppi:"/economic-events/cpi/", pce:"/economic-events/cpi/", fomc:"/economic-events/fomc/", "fed-speakers":"/economic-events/fed-speakers/", nfp:"/economic-events/nfp/", "crude-oil-inventories":"/economic-events/crude-oil-inventories/" };
const SYM_URL = { ES:"/markets/es-futures/", NQ:"/markets/nq-futures/", YM:"/markets/ym-futures/", RTY:"/markets/rty-futures/", GC:"/markets/gold-futures/", SI:"/markets/gold-futures/", HG:"/markets/gold-futures/", CL:"/markets/crude-oil-futures/", NG:"/markets/crude-oil-futures/", ZB:"/markets/bond-futures/", BTC:"/markets/bitcoin-futures/" };
function contextHref(item) {
  const B = process.env.WP_BASE;
  if (item.event && EVT_URL[item.event]) return B + EVT_URL[item.event];
  if (item.symbols && item.symbols.length && SYM_URL[item.symbols[0]]) return B + SYM_URL[item.symbols[0]];
  if (item.sector === "prop") return B + "/best-futures-prop-firms/";
  if (item.sector === "software") return B + "/futures-software/";
  return B + "/futures-economic-calendar/";
}

function esc(s) { return String(s || "").replace(/"/g, "&quot;"); }

const HOT_BADGE = `<span style="background:#DC2626;color:#fff;font-size:9px;font-weight:900;letter-spacing:.05em;padding:2px 6px;border-radius:4px;">HOT</span>`;

function renderRow(item, id) {
  const a = ACCENTS[item.importance] || ACCENTS.normal;
  const href = contextHref(item);
  const hot = item.importance === "hot";
  const tag = hot ? HOT_BADGE + `<span style="font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.04em;color:${a.fg};">Market mover</span>` : "";
  return `<a class="pot-pulse-row" data-hot="${hot ? 1 : 0}" data-news-id="${id}" data-link="${esc(item.link)}" data-published="${esc(item.published)}" href="${href}" style="display:flex;flex-direction:column;gap:6px;padding:15px 4px;border-bottom:1px solid #EDF1F6;text-decoration:none;">`
    + `<span style="display:flex;align-items:center;gap:9px;">`
      + `<span style="width:7px;height:7px;border-radius:50%;background:${a.line};flex-shrink:0;"></span>`
      + `<span style="font-size:11px;font-weight:700;color:#8A94A6;">${stamp(item.published)}</span>`
      + tag
    + `</span>`
    + `<span style="font-size:15px;font-weight:800;color:#071A2F;line-height:1.34;">${item.headline}</span>`
    + `<span style="font-size:13px;font-weight:500;color:#52607A;line-height:1.5;">${item.summary}</span>`
    + `</a>`;
}

// compact row for the market/hub "pulse" spots: headline only, links back to the calendar (hub-and-spoke)
function renderRowCompact(item, id) {
  const a = ACCENTS[item.importance] || ACCENTS.normal;
  const cal = process.env.WP_BASE + "/futures-economic-calendar/";
  const hot = item.importance === "hot";
  return `<a class="pot-pulse-row" data-hot="${hot ? 1 : 0}" data-news-id="${id}" data-link="${esc(item.link)}" data-published="${esc(item.published)}" href="${cal}" style="display:flex;align-items:center;gap:11px;padding:11px 14px;border:1px solid #E4E9F0;border-left:3px solid ${a.line};border-radius:9px;background:#fff;text-decoration:none;margin-bottom:8px;">`
    + `<span style="flex-shrink:0;white-space:nowrap;font-size:10px;font-weight:800;color:${a.fg};background:${a.bg};border-radius:5px;padding:3px 8px;">${stamp(item.published)}</span>`
    + (hot ? HOT_BADGE : "")
    + `<span style="color:#071A2F;font-size:13px;font-weight:700;line-height:1.35;">${item.headline}</span>`
    + `</a>`;
}

// symbol -> [market page id, pulse zone] (all 28 contracts)
const SYM_PAGE = {
  ES:[455,"mkt-es-pulse"], NQ:[456,"mkt-nq-pulse"], YM:[457,"mkt-ym-pulse"], RTY:[458,"mkt-rty-pulse"],
  GC:[459,"mkt-gc-pulse"], CL:[460,"mkt-cl-pulse"], ZB:[461,"mkt-bonds-pulse"], BTC:[462,"mkt-btc-pulse"],
  "6E":[482,"mkt-6e-pulse"], NG:[483,"mkt-ng-pulse"], SI:[484,"mkt-si-pulse"], HG:[485,"mkt-hg-pulse"],
  "6B":[486,"mkt-6b-pulse"], "6J":[487,"mkt-6j-pulse"],
  ZC:[488,"mkt-zc-pulse"], ZS:[489,"mkt-zs-pulse"], ZW:[490,"mkt-zw-pulse"], KC:[491,"mkt-kc-pulse"],
  SB:[492,"mkt-sb-pulse"], CT:[493,"mkt-ct-pulse"], LE:[494,"mkt-le-pulse"], GF:[495,"mkt-gf-pulse"],
  HE:[496,"mkt-he-pulse"], ZO:[497,"mkt-zo-pulse"], ZM:[498,"mkt-zm-pulse"], ZL:[499,"mkt-zl-pulse"],
  CC:[500,"mkt-cc-pulse"], OJ:[501,"mkt-oj-pulse"]
};
// macro spillover reaches ONLY the broadly macro/risk-driven contracts: index, bonds, gold, crypto.
// Energy, metals(silver/copper), FX, grains/softs/livestock trade on their OWN fundamentals -> own news only.
const ALL_MKT = [[455,"mkt-es-pulse"],[456,"mkt-nq-pulse"],[457,"mkt-ym-pulse"],[458,"mkt-rty-pulse"],[459,"mkt-gc-pulse"],[461,"mkt-bonds-pulse"],[462,"mkt-btc-pulse"]];
const BIG_EVENTS = ["cpi","ppi","pce","nfp","fomc","fed-speakers"];
// theme -> [[event page id, zone prefix], ...] so guide pages stay full of THEMATICALLY relevant news,
// not just the once-a-month exact release. A "Fed on inflation" story hits both CPI and FOMC/fed-speakers.
const THEME_PAGE = { inflation:[[449,"calendar-cpi"]], fed:[[450,"calendar-fomc"],[453,"calendar-fed-speakers"]], jobs:[[451,"calendar-nfp"]], oil:[[452,"calendar-crude-oil-inventories"]] };

function routeTargets(item) {
  const t = [{ page: 447, zone: "calendar-latest-stories", mode: "prepend", cap: 30, style: "full" }];
  if (item.importance === "hot") t.push({ page: 447, zone: "calendar-hot-story", mode: "replace", cap: 1, style: "full" });
  // guide pages: route by THEME so each stays full of relevant news (inflation->CPI, fed->FOMC+fed-speakers, etc.)
  const epDone = new Set();
  for (const th of (item.themes || [])) {
    for (const [pid, prefix] of (THEME_PAGE[th] || [])) {
      if (epDone.has(prefix)) continue;
      epDone.add(prefix);
      t.push({ page: pid, zone: prefix + "-latest-story", mode: "prepend", cap: 6, style: "full" });
      if (item.importance === "hot") t.push({ page: pid, zone: prefix + "-hot-story", mode: "replace", cap: 1, style: "full" });
    }
  }
  // fan-out: each tagged symbol -> its market page pulse (compact)
  const done = new Set();
  for (const s of (item.symbols || [])) {
    const mp = SYM_PAGE[s];
    if (mp && !done.has(mp[1])) { done.add(mp[1]); t.push({ page: mp[0], zone: mp[1], mode: "prepend", cap: 4, style: "compact" }); }
  }
  // macro spillover: ONLY scheduled market-wide releases (jobs/CPI/Fed) reach the macro pages.
  // A symbol-specific mover (a silver crash, an oil spike) is NOT spilled - it stays on its own page.
  if (BIG_EVENTS.includes(item.event)) {
    for (const [pid, zone] of ALL_MKT) {
      if (!done.has(zone)) { done.add(zone); t.push({ page: pid, zone, mode: "prepend", cap: 4, style: "compact" }); }
    }
  }
  // (prop-firm & software hubs intentionally get NO news fan-out - those pages focus on reviews.
  //  General market news still flows to the calendar, market pages, brief and homepage below.)
  // general "latest futures" pulses: homepage (Elementor), markets hub, daily brief
  t.push({ page: 454, zone: "market-pulse", mode: "prepend", cap: 5, style: "compact" });
  t.push({ page: 445, zone: "daily-brief-pulse", mode: "prepend", cap: 5, style: "compact" });
  t.push({ page: 43, zone: "home-today", mode: "prepend", cap: 4, style: "compact" });
  return t;
}

function spliceZone(html, zone, builder) {
  const s = `<!--ZONE:${zone}-START-->`, e = `<!--ZONE:${zone}-END-->`;
  const i = html.indexOf(s), j = html.indexOf(e);
  if (i === -1 || j === -1) return null;
  const inner = html.slice(i + s.length, j);
  return html.slice(0, i + s.length) + builder(inner) + html.slice(j);
}

// merge the new row with existing rows, dedupe by link, sort HOT-first then newest-first, cap.
function mergeAndSort(newRow, inner, cap) {
  const existing = (inner.match(/<a class="pot-pulse-row"[\s\S]*?<\/a>/g) || [])
    .filter(x => !/being wired up|Live soon|live data/i.test(x));
  const all = [newRow, ...existing];
  const seen = new Set();
  const uniq = all.filter(r => {
    const l = (r.match(/data-link="([^"]*)"/) || [])[1] || Math.random().toString();
    if (seen.has(l)) return false; seen.add(l); return true;
  });
  uniq.sort((x, y) => {
    const hx = /data-hot="1"/.test(x) ? 0 : 1, hy = /data-hot="1"/.test(y) ? 0 : 1;
    if (hx !== hy) return hx - hy;
    const px = (x.match(/data-published="([^"]*)"/) || [])[1] || "";
    const py = (y.match(/data-published="([^"]*)"/) || [])[1] || "";
    return py.localeCompare(px); // newest first
  });
  return uniq.slice(0, cap).join("\n");
}

export default defineComponent({
  async run({ steps, $ }) {
    // oldest-first: each item is prepended below, so newest ends up on top
    const items = (steps.haiku.$return_value || []).slice().sort((a, b) => pubTs(a) - pubTs(b));
    if (!items.length) return $.flow.exit("nothing to post");
    const BASE = process.env.WP_BASE;
    const AUTH = "Basic " + Buffer.from(`${process.env.WP_USER}:${process.env.WP_APP_PASS}`).toString("base64");

    const byPage = {};
    const posted = [];
    for (const item of items) {
      const id = "n" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
      item._id = id;
      const targets = routeTargets(item);
      for (const tg of targets) (byPage[tg.page] = byPage[tg.page] || []).push({ ...tg, item });
      posted.push({ id, headline: item.headline, importance: item.importance, source: item.source });
    }

    // Recursively find the Elementor HTML widget containing a zone and update it.
    function updateEdataZone(elements, zone, builder) {
      const s = `<!--ZONE:${zone}-START-->`, e = `<!--ZONE:${zone}-END-->`;
      for (const el of elements || []) {
        if (el.settings && typeof el.settings.html === "string" && el.settings.html.includes(s)) {
          const next = spliceZone(el.settings.html, zone, builder);
          if (next) { el.settings.html = next; return true; }
        }
        if (el.elements && updateEdataZone(el.elements, zone, builder)) return true;
      }
      return false;
    }

    for (const pageId of Object.keys(byPage)) {
      const r = await fetch(`${BASE}/wp-json/wp/v2/pages/${pageId}?context=edit`, { headers: { Authorization: AUTH } });
      const pg = await r.json();
      const isHomepage = String(pageId) === "43";

      // Detect Elementor pages (they have _elementor_data in meta)
      let edata = null;
      const edataRaw = pg.meta && pg.meta._elementor_data;
      if (edataRaw && edataRaw.length > 10) {
        try { edata = JSON.parse(edataRaw); } catch (e) {}
      }

      let html = "";
      if (isHomepage && edata) {
        try { html = edata[0].elements[0].settings.html || ""; } catch (e) { html = ""; }
      } else {
        html = (pg.content && pg.content.raw) || "";
      }

      let edataUpdated = false;
      for (const { zone, mode, cap, item, style } of byPage[pageId]) {
        const row = style === "compact" ? renderRowCompact(item, item._id) : renderRow(item, item._id);
        const builder = (inner) => mode === "replace" ? row : mergeAndSort(row, inner, cap);

        if (isHomepage && edata) {
          // Homepage: zone lives at a known Elementor path
          const next = spliceZone(html, zone, builder);
          if (next) { html = next; edataUpdated = true; }
        } else if (edata && updateEdataZone(edata, zone, builder)) {
          // Other Elementor pages: found & updated the zone recursively
          edataUpdated = true;
        } else {
          // Non-Elementor pages (Calendar, Daily Brief, etc.): update content.raw
          const next = spliceZone(html, zone, builder);
          if (next) html = next;
        }
      }

      let body;
      if (isHomepage && edata && edataUpdated) {
        edata[0].elements[0].settings.html = html;
        body = JSON.stringify({ meta: { _elementor_data: JSON.stringify(edata) } });
      } else if (edata && edataUpdated) {
        body = JSON.stringify({ meta: { _elementor_data: JSON.stringify(edata) } });
      } else {
        body = JSON.stringify({ content: html });
      }

      await fetch(`${BASE}/wp-json/wp/v2/pages/${pageId}`, {
        method: "POST",
        headers: { Authorization: AUTH, "content-type": "application/json" },
        body
      });
    }

    // Elementor cache clear
    try { await fetch(`${BASE}/wp-json/elementor/v1/cache`, { method: "DELETE", headers: { Authorization: AUTH } }); } catch (e) {}
    // LiteSpeed Cache purge — REST API (works server-side; admin.php requires browser cookies)
    try { await fetch(`${BASE}/wp-json/litespeed/v1/purge/all`, { method: "POST", headers: { Authorization: AUTH, "content-type": "application/json" }, body: "{}" }); } catch (e) {}
    // Fallback: also hit the admin purge URL in case the REST endpoint isn't enabled
    try { await fetch(`${BASE}/wp-admin/admin-ajax.php`, { method: "POST", headers: { Authorization: AUTH, "content-type": "application/x-www-form-urlencoded" }, body: "action=litespeed_purge_all" }); } catch (e) {}

    return posted;
  }
});
