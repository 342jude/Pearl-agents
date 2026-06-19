"""
Pearl Heartbeat — daily freshness check for all automated agents.
Reads key pages, finds the most-recent data-published timestamp, and
Slack-alerts if anything is stale.  Runs via GitHub Actions at 13:00 UTC
(9 AM ET) every weekday so you hear about broken agents before markets
close, not 9 days later.

Env: WP_BASE, WP_USER, WP_APP_PASS, SLACK_WEBHOOK_URL
"""
import urllib.request, json, base64, os, re
from datetime import datetime, date, timedelta, timezone, tzinfo

# --- ET timezone ---
def _nth_sun(y,mo,n):
    d=date(y,mo,1); d+=timedelta((6-d.weekday())%7); return d+timedelta(7*(n-1))
class _ET(tzinfo):
    def utcoffset(self,dt):
        dd=dt.date(); h=-4 if _nth_sun(dt.year,3,2)<=dd<_nth_sun(dt.year,11,1) else -5
        return timedelta(hours=h)
    def tzname(self,dt): return 'ET'
    def dst(self,dt): return timedelta(0)
ET=_ET()

BASE=os.environ['WP_BASE']
AUTH='Basic '+base64.b64encode(('%s:%s'%(os.environ['WP_USER'],os.environ['WP_APP_PASS'])).encode()).decode()
WPH={'Authorization':AUTH,'User-Agent':'Mozilla/5.0'}

def wp_get(pid):
    u='%s/wp-json/wp/v2/pages/%d?context=edit'%(BASE,pid)
    r=urllib.request.Request(u,headers=WPH)
    return json.loads(urllib.request.urlopen(r,timeout=20).read())

def latest_published(html):
    """Find the most recent data-published timestamp in a zone's HTML."""
    times=[]
    for m in re.finditer(r'data-published="([^"]+)"',html):
        try:
            t=datetime.fromisoformat(m.group(1).replace('Z','+00:00'))
            times.append(t)
        except: pass
    return max(times) if times else None

def hours_ago(dt):
    if dt is None: return None
    now=datetime.now(timezone.utc)
    diff=now-dt.astimezone(timezone.utc)
    return round(diff.total_seconds()/3600,1)

# ----------------------------------------------------------------
# CHECKS
# ----------------------------------------------------------------
# 1. News Desk — Calendar page (447) is the de-dup memory; every run writes to it.
#    If its newest story is >10 h old on a weekday, the news agent is broken.
# 2. Daily Bias — page 445 has a zone timestamp baked into the market-context banner.
#    We look for the stamp text like "Jun 19" written by daily_bias.py.
# 3. Spot-check a few market pages: Gold (459), ES (455) — should have news <24h.

checks = [
    {'name':'News Desk (Calendar)',  'pid':447, 'zone':'calendar-latest-stories', 'stale_h':10,  'match':'data-published'},
    {'name':'News Desk (Gold page)', 'pid':459, 'zone':'mkt-gc-pulse',            'stale_h':24,  'match':'data-published'},
    {'name':'News Desk (ES page)',   'pid':455, 'zone':'mkt-es-pulse',            'stale_h':24,  'match':'data-published'},
    {'name':'Daily Bias',            'pid':445, 'zone':'daily-brief-read',        'stale_h':10,  'match':'data-published'},
    {'name':'Events Banner',         'pid':445, 'zone':'week-ahead',              'stale_h':None,'match':'radar-chip'},
]

now_et=datetime.now(ET)
is_weekday=(now_et.weekday()<5)   # Mon-Fri

results=[]
for ck in checks:
    try:
        pg=wp_get(ck['pid'])
        raw=(pg.get('content',{}).get('raw',''))
        s='<!--ZONE:%s-START-->'%ck['zone']
        e='<!--ZONE:%s-END-->'%ck['zone']
        i=raw.find(s); j=raw.find(e)
        zone_html=raw[i+len(s):j] if i>=0 and j>=0 else ''

        if ck['match']=='data-published':
            latest=latest_published(zone_html)
            age=hours_ago(latest)
            has_content=bool(zone_html.strip())
            if latest is None:
                status='⚠️ NO DATA' if has_content else '⚠️ EMPTY'
                stale=True
            elif ck['stale_h'] and age>ck['stale_h'] and is_weekday:
                status='⚠️ STALE %.0fh ago'%age
                stale=True
            else:
                status='✅ %.1fh ago'%age
                stale=False
        else:
            # just check if the zone has any content
            has=ck['match'] in zone_html
            status='✅ present' if has else '⚠️ EMPTY'
            stale=not has

        results.append({'name':ck['name'],'status':status,'stale':stale})
        print('%s: %s'%(ck['name'],status))
    except Exception as ex:
        results.append({'name':ck['name'],'status':'❌ ERROR: %s'%str(ex)[:80],'stale':True})
        print('%s: ERROR %s'%(ck['name'],ex))

# ----------------------------------------------------------------
# SLACK REPORT
# ----------------------------------------------------------------
hook=os.environ.get('SLACK_WEBHOOK_URL','')
if not hook:
    print('No SLACK_WEBHOOK_URL — skipping Slack')
else:
    stale_count=sum(1 for r in results if r['stale'])
    icon='✅' if stale_count==0 else '⚠️'
    lines=[('%s *%s:* %s'%('🔴' if r['stale'] else '🟢',r['name'],r['status'])) for r in results]
    header='%s *Pearl Heartbeat — %s ET*'%(icon,now_et.strftime('%b %d %H:%M'))
    if stale_count:
        header+=' — *%d agent%s stale*'%(stale_count,'s' if stale_count>1 else '')
        header+='\nGo to: https://github.com/342jude/Pearl-agents/actions to check run logs.'
    else:
        header+=' — all agents live'
    msg={'text':header+'\n'+'\n'.join(lines)}
    req=urllib.request.Request(hook,data=json.dumps(msg).encode(),
        headers={'content-type':'application/json'},method='POST')
    urllib.request.urlopen(req,timeout=15).read()
    print('Slack sent.')

if any(r['stale'] for r in results):
    raise SystemExit('Heartbeat found stale agents — see above.')
