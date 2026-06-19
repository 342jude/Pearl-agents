#!/usr/bin/env python3
"""
update_hours_page.py
Runs January 2 each year via GitHub Actions.
Recomputes CME holiday dates and futures rollover dates for the new year,
then patches the Futures Trading Hours page (ID 1134) in-place.
No external packages required — stdlib only.
"""
import sys, os, re, datetime, calendar

sys.path.insert(0, os.path.dirname(__file__))
from pf_lib import req

# ── date helpers ──────────────────────────────────────────────────────────────

def nth_weekday(year, month, weekday, n=1):
    """nth occurrence (0=Mon…4=Fri…6=Sun) of weekday in month. n=-1 = last."""
    if n > 0:
        d = datetime.date(year, month, 1)
        d += datetime.timedelta((weekday - d.weekday()) % 7)
        d += datetime.timedelta(weeks=n - 1)
        return d
    else:
        d = datetime.date(year, month, calendar.monthrange(year, month)[1])
        d -= datetime.timedelta((d.weekday() - weekday) % 7)
        return d

def sub_biz(d, n):
    """Return date n business days before d."""
    while n > 0:
        d -= datetime.timedelta(1)
        if d.weekday() < 5:
            n -= 1
    return d

def end_of_month(year, month):
    return datetime.date(year, month, calendar.monthrange(year, month)[1])

def last_biz_of_month(year, month):
    d = end_of_month(year, month)
    while d.weekday() >= 5:
        d -= datetime.timedelta(1)
    return d

def observed(d):
    if d.weekday() == 5: return d - datetime.timedelta(1)  # Sat → Fri
    if d.weekday() == 6: return d + datetime.timedelta(1)  # Sun → Mon
    return d

def easter(year):
    """Meeus/Jones/Butcher Easter Sunday algorithm (stdlib only)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    mo = (h + l - 7*m + 114) // 31
    dy = (h + l - 7*m + 114) % 31 + 1
    return datetime.date(year, mo, dy)

WD = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

def dfmt(d):
    return f"{WD[d.weekday()]} {MN[d.month-1]} {d.day}"

def dfmt_long(d):
    return f"{WD[d.weekday()]} {MN[d.month-1]} {d.day}, {d.year}"

# ── CME holiday computation ───────────────────────────────────────────────────

def cme_holidays(year):
    """
    Return sorted list of (date, name, note, css_class, badge) for `year`.
    Includes next year's New Year's Day. Weekday dates only.
    """
    events = []

    def add(d, name, note, cls, badge):
        if d.weekday() < 5:
            events.append((d, name, note, cls, badge))

    # ── Full closures ─────────────────────────────────────────────────────────
    add(observed(datetime.date(year, 1, 1)),
        "New Year's Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    add(nth_weekday(year, 1, 0, 3),
        "Martin Luther King Jr. Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    add(nth_weekday(year, 2, 0, 3),
        "Presidents' Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    add(easter(year) - datetime.timedelta(2),
        "Good Friday",
        "CME equity, metal, and energy futures closed",
        "hol-closed", "CLOSED")

    add(nth_weekday(year, 5, 0, -1),
        "Memorial Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    add(observed(datetime.date(year, 6, 19)),
        "Juneteenth National Independence Day",
        "US equity markets closed; ES/NQ futures open with very thin liquidity",
        "hol-closed", "CLOSED")

    july4 = datetime.date(year, 7, 4)
    if july4.weekday() == 5:      # Saturday → Friday early close
        add(july4 - datetime.timedelta(1),
            "Independence Day (observed early close)",
            "Jul 4 falls Saturday — CME closes equity, metal, and energy at 1:00 PM ET",
            "hol-early", "Early close 1 PM")
    elif july4.weekday() == 6:    # Sunday → Monday full close
        add(july4 + datetime.timedelta(1),
            "Independence Day (observed)",
            "All US futures markets closed",
            "hol-closed", "CLOSED")
    else:
        add(july4,
            "Independence Day",
            "All US futures markets closed",
            "hol-closed", "CLOSED")

    add(nth_weekday(year, 9, 0, 1),
        "Labor Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    thanksgiving = nth_weekday(year, 11, 3, 4)
    add(thanksgiving,
        "Thanksgiving Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    add(observed(datetime.date(year, 12, 25)),
        "Christmas Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    # ── Early closes ──────────────────────────────────────────────────────────
    day_after_tg = thanksgiving + datetime.timedelta(1)
    add(day_after_tg,
        "Day After Thanksgiving",
        "CME equity, metals, energy early close 1:00 PM ET — thin volume all day",
        "hol-early", "Early close 1 PM")

    xmas_eve = datetime.date(year, 12, 24)
    add(xmas_eve,
        "Christmas Eve",
        "CME equity, metals, energy early close 1:00 PM ET",
        "hol-early", "Early close 1 PM")

    nye = datetime.date(year, 12, 31)
    add(nye,
        "New Year's Eve",
        "CME equity, metals, energy early close 1:00 PM ET",
        "hol-early", "Early close 1 PM")

    # Next year's New Year's Day
    ny1 = observed(datetime.date(year + 1, 1, 1))
    add(ny1,
        "New Year's Day",
        "All US futures markets closed",
        "hol-closed", "CLOSED")

    events.sort(key=lambda x: x[0])
    return events

# ── rollover date computation ─────────────────────────────────────────────────

MONTH_CODE = {3:'H', 6:'M', 9:'U', 12:'Z'}
QUARTER_MONTHS = [3, 6, 9, 12]

def equity_roll(year, qm):
    """ES/NQ/YM/RTY: expire 3rd Friday, roll Thu-Fri 7-8 days before."""
    expiry = nth_weekday(year, qm, 4, 3)          # 3rd Friday
    roll_thu = expiry - datetime.timedelta(8)
    roll_fri = expiry - datetime.timedelta(7)
    return expiry, roll_thu, roll_fri

def rates_roll(year, qm):
    """ZB/ZN: roll week = 3rd Fri week of delivery month; last trade ~6 biz days before month end."""
    third_fri = nth_weekday(year, qm, 4, 3)
    roll_thu = third_fri - datetime.timedelta(1)
    roll_fri = third_fri
    ltd = sub_biz(end_of_month(year, qm), 6)
    return ltd, roll_thu, roll_fri

def fx_roll(year, qm):
    """6E: expires 2 biz days before 3rd Wednesday; roll week same as equity."""
    third_wed = nth_weekday(year, qm, 2, 3)
    expiry = sub_biz(third_wed, 2)
    _, roll_thu, roll_fri = equity_roll(year, qm)
    return expiry, roll_thu, roll_fri

def btc_roll(year, qm):
    """BTC CME: last Friday of delivery month; roll 7-8 days before."""
    expiry = nth_weekday(year, qm, 4, -1)
    roll_thu = expiry - datetime.timedelta(8)
    roll_fri = expiry - datetime.timedelta(7)
    return expiry, roll_thu, roll_fri

def gold_rollovers(year):
    """GC: active even months. Last trade = 3rd-to-last biz day of delivery month."""
    today = datetime.date.today()
    out = []
    for mo in [2, 4, 6, 8, 10, 12]:
        ltd = sub_biz(end_of_month(year, mo), 2)
        if ltd > today:
            out.append((MN[mo-1], ltd))
    return out[:3]

def crude_rollovers(year):
    """CL: last trade = 3 biz days before the 25th of the month before delivery."""
    today = datetime.date.today()
    out = []
    for delivery_mo in range(1, 13):
        prior_mo = delivery_mo - 1 if delivery_mo > 1 else 12
        prior_yr = year if delivery_mo > 1 else year - 1
        d25 = datetime.date(prior_yr, prior_mo, 25)
        ltd = sub_biz(d25, 3)
        contract = f"{MN[delivery_mo-1]} {year}"
        if prior_yr == year and ltd > today and len(out) < 5:
            out.append((contract, ltd))
    return out

# ── HTML builders ─────────────────────────────────────────────────────────────

def chip(text, cls):
    """Render a status chip matching the new .th-chip design."""
    if cls == 'hol-closed':
        return f'<span class="th-chip chip-closed">{text}</span>'
    return f'<span class="th-chip chip-early">{text}</span>'

def build_holiday_section(year):
    """Build the holiday section matching the .th-hol-board row design."""
    events = cme_holidays(year)
    rows = []
    for d, name, note, _, badge in events:
        date_str = dfmt(d) if d.year == year else f"{dfmt(d)} {d.year}"
        cls = 'hol-closed' if badge == 'CLOSED' else 'hol-early'
        rows.append(
            f'      <div class="th-hol-row">\n'
            f'        <span class="th-hol-date">{date_str}</span>\n'
            f'        <div><span class="th-hol-name">{name}</span>'
            f'<span class="th-hol-note">{note}</span></div>\n'
            f'        <div>{chip(badge, cls)}</div>\n'
            f'      </div>'
        )
    return (
        f'<section id="holidays-{year}">\n'
        f'      <div class="th-section-head">\n'
        f'        <div>\n'
        f'          <h2>{year} Holiday &amp; Early-Close Calendar</h2>\n'
        f'          <p class="th-intro">Remaining CME holiday closures and early-close dates for {year}. '
        f'On early-close days liquidity drops sharply after 11:30 AM ET &mdash; size down or stand aside from noon onward.</p>\n'
        f'        </div>\n'
        f'      </div>\n'
        f'      <div class="th-hol-board">\n'
        + '\n'.join(rows) + '\n'
        f'      </div>\n'
        f'    </section>'
    )

def roll_row(sym_note, active_str, next_str):
    """Build a .th-roll-row matching the new design."""
    return (
        f'      <div class="th-roll-row">\n'
        f'        <div><b>{sym_note[0]}</b><span>{sym_note[1]}</span></div>\n'
        f'        <div><strong>{active_str[0]}</strong><span>{active_str[1]}</span></div>\n'
        f'        <div><strong>{next_str[0]}</strong><span>{next_str[1]}</span></div>\n'
        f'      </div>'
    )

def build_rollover_section(year):
    """Build the rollover section matching the .th-roll-board row design."""
    today = datetime.date.today()
    upcoming = [m for m in QUARTER_MONTHS
                if nth_weekday(year, m, 4, 3) >= today]
    if not upcoming:
        upcoming = QUARTER_MONTHS

    aqm = upcoming[0]
    nqm = upcoming[1] if len(upcoming) > 1 else None
    act_code = MONTH_CODE[aqm]; act_mn = MN[aqm-1]

    # Equity
    act_exp, act_thu, act_fri = equity_roll(year, aqm)
    if nqm:
        nx_exp, nx_thu, nx_fri = equity_roll(year, nqm)
        nx_code = MONTH_CODE[nqm]; nx_mn = MN[nqm-1]
        eq_active = (f"{act_mn} {year} ({act_code}) active", f"Roll week {dfmt(act_thu)}–{act_fri.day} · Expires {dfmt_long(act_exp)}")
        eq_next   = (f"{nx_mn} {year} ({nx_code}) next", f"Roll week {dfmt(nx_thu)}–{nx_fri.day} · Expires {dfmt_long(nx_exp)}")
    else:
        eq_active = (f"{act_mn} {year} ({act_code}) active", f"Roll week {dfmt(act_thu)}–{act_fri.day} · Expires {dfmt_long(act_exp)}")
        eq_next   = ("See CME for next quarter", "")

    # Gold
    gc_months = gold_rollovers(year)
    gc_active_str = " · ".join(f"{mn} last trade {dfmt_long(ltd)}" for mn, ltd in gc_months[:2])
    gc_next_str   = f"{gc_months[2][0]} last trade {dfmt_long(gc_months[2][1])}" if len(gc_months) > 2 else "SI/HG roll ~5 days before month end"

    # Crude
    cl_items = crude_rollovers(year)
    cl_active_str = " · ".join(f"CL {c} last trade {dfmt_long(ltd)}" for c, ltd in cl_items[:2]) if cl_items else "See CME"
    cl_next_str   = " · ".join(f"CL {c} last trade {dfmt_long(ltd)}" for c, ltd in cl_items[2:4]) if len(cl_items) > 2 else "NG rolls same month, ~3 days earlier"

    # Rates
    act_ltd, act_rth, act_rfr = rates_roll(year, aqm)
    if nqm:
        nx_ltd, nx_rth, nx_rfr = rates_roll(year, nqm)
        rt_active = (f"{act_mn} {year} ({act_code}) active", f"Roll week {dfmt(act_rth)}–{act_rfr.day} · Last trade {dfmt_long(act_ltd)}")
        rt_next   = (f"{nx_mn} {year} ({nx_code}) next", f"Roll week {dfmt(nx_rth)}–{nx_rfr.day} · Last trade {dfmt_long(nx_ltd)}")
    else:
        rt_active = (f"{act_mn} {year} ({act_code}) active", f"Roll week {dfmt(act_rth)}–{act_rfr.day} · Last trade {dfmt_long(act_ltd)}")
        rt_next   = ("See CME for next quarter", "")

    # 6E
    fx_exp, fx_thu, fx_fri = fx_roll(year, aqm)
    fx_active = (f"{act_mn} {year} ({act_code}) active", f"Roll week {dfmt(fx_thu)}–{fx_fri.day} · Expires {dfmt_long(fx_exp)}")
    fx_next   = ("Rolls same week as equity futures", "Check broker for next quarter contract")

    # BTC
    btc_exp, btc_thu, btc_fri = btc_roll(year, aqm)
    btc_active = (f"{act_mn} {year} ({act_code}) active", f"Roll week {dfmt(btc_thu)}–{btc_fri.day} · Expires {dfmt_long(btc_exp)}")
    btc_next   = ("Spot trades weekends — check Sunday CME open for gap", "")

    rows = [
        roll_row(("ES · NQ · YM · RTY", "CME Equity Index — quarterly"), eq_active, eq_next),
        roll_row(("GC · SI · HG", "COMEX Metals — monthly active months"), (gc_active_str, "Active even months: Feb, Apr, Jun, Aug, Oct, Dec"), (gc_next_str, "Watch open interest shift on CME site")),
        roll_row(("CL · NG", "NYMEX Energy — monthly"), (cl_active_str, "Expires ~3 biz days before 25th of prior month"), (cl_next_str, "NG rolls same month as CL, ~3 days earlier")),
        roll_row(("ZB · ZN", "CBOT Rates — quarterly"), rt_active, rt_next),
        roll_row(("6E", "CME Euro FX — quarterly"), fx_active, fx_next),
        roll_row(("BTC", "CME Crypto — quarterly"), btc_active, btc_next),
    ]

    return (
        f'<section id="rollover-{year}">\n'
        f'      <div class="th-section-head">\n'
        f'        <div>\n'
        f'          <h2>{year} Rollover Calendar</h2>\n'
        f'          <p class="th-intro">When volume shifts from the front-month to the next contract. '
        f'Roll week is when open interest moves &mdash; usually the Thursday&ndash;Friday about 8 days before expiry. '
        f'Always confirm the active contract with your broker before entering.</p>\n'
        f'        </div>\n'
        f'        <a href="/futures-contract-rollover/" class="th-tiny-link">Full Rollover Guide</a>\n'
        f'      </div>\n'
        f'      <div class="th-roll-board">\n'
        + '\n'.join(rows) + '\n'
        f'      </div>\n'
        f'    </section>'
    )

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    year = datetime.date.today().year
    print(f'[update-hours] Running for year {year}')

    pg = req('GET', '/wp-json/wp/v2/pages/1134?context=edit')
    raw = pg.get('content', {}).get('raw', '')
    if not raw:
        print('ERROR: page content empty'); sys.exit(1)

    original_len = len(raw)

    # 1. Badge year
    raw = re.sub(r'Updated for \d{4}', f'Updated for {year}', raw)

    # 2. Holiday section (regex matches <section id="holidays-YEAR"> ... </section>)
    new_hol = build_holiday_section(year)
    raw, n_hol = re.subn(
        r'<section id="holidays-\d+">.*?</section>',
        new_hol, raw, flags=re.DOTALL
    )
    if n_hol == 0:
        print('WARNING: holidays section not found — page may need manual update'); sys.exit(1)

    # 3. Rollover section
    new_roll = build_rollover_section(year)
    raw, n_roll = re.subn(
        r'<section id="rollover-\d+">.*?</section>',
        new_roll, raw, flags=re.DOTALL
    )
    if n_roll == 0:
        print('WARNING: rollover section not found — page may need manual update'); sys.exit(1)

    result = req('POST', '/wp-json/wp/v2/pages/1134', {
        'content': raw,
        'excerpt': (
            f'Every CME, CBOT, COMEX, and NYMEX futures contract session time in one place — '
            f'Globex hours, day session windows, settlement times, {year} holiday closures, '
            f'and quarterly rollover dates.'
        ),
        'status': 'publish'
    })
    link = result.get('link', '—')
    new_len = len(result.get('content', {}).get('raw', ''))
    print(f'[update-hours] Done — {link}')
    print(f'[update-hours] Content: {original_len} → {new_len} chars')
    print(f'[update-hours] Holiday events: {len(cme_holidays(year))}')

if __name__ == '__main__':
    main()
