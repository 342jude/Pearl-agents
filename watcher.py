# Pearl Watcher — link/closure health-check for prop-firm + software review pages.
# Self-discovering: reads the live site, finds every review page, extracts its outbound
# (official/affiliate) link, health-checks it, and posts any problems to Slack.
# READ-ONLY on the site (never writes). Free, runs on GitHub Actions.
# Env: WP_BASE, WP_USER, WP_APP_PASS, and SLACK_WATCH_WEBHOOK_URL (or falls back to SLACK_WEBHOOK_URL).
import os, re, json, time, base64, urllib.request, urllib.error
from urllib.parse import urlparse
from collections import Counter

BASE=os.environ['WP_BASE']
AUTH='Basic '+base64.b64encode(('%s:%s'%(os.environ['WP_USER'],os.environ['WP_APP_PASS'])).encode()).decode()
WPH={'Authorization':AUTH,'User-Agent':'Mozilla/5.0'}
SLACK=os.environ.get('SLACK_WATCH_WEBHOOK_URL') or os.environ.get('SLACK_BIAS_WEBHOOK_URL') or os.environ.get('SLACK_WEBHOOK_URL')
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
# domains that are never the firm/tool's own site (social, aggregators, infra)
SKIP=('pearloftrades.com','w3.org','schema.org','googleapis.com','gstatic.com','gravatar.com','wordpress.org',
      'twitter.com','x.com','facebook.com','instagram.com','youtube.com','youtu.be','linkedin.com',
      't.me','discord.gg','discord.com','trustpilot.com','reddit.com','tiktok.com')
def is_skip(host):
    host=host.lower()
    if host.startswith('www.'): host=host[4:]
    return any(host==s or host.endswith('.'+s) for s in SKIP)   # exact-domain match, not substring

def wp(path):
    return json.loads(urllib.request.urlopen(urllib.request.Request(BASE+path,headers=WPH),timeout=30).read())

# 1) discover all pages, keep the review pages
pages=[]; pg=1
while True:
    batch=wp('/wp-json/wp/v2/pages?per_page=100&page=%d&_fields=id,link,title'%pg)
    if not batch: break
    pages+=batch
    if len(batch)<100: break
    pg+=1
def section(link):
    p=urlparse(link).path.strip('/').split('/')
    if len(p)>=2 and p[0]=='best-futures-prop-firms' and p[1] not in ('rating-methodology','news'): return 'prop'
    if len(p)>=2 and p[0]=='futures-software' and p[1]!='news': return 'software'
    return None
reviews=[(p['id'],p['link'],section(p['link']),re.sub('<[^>]+>','',(p.get('title',{}) or {}).get('rendered','')).strip())
         for p in pages if section(p['link'])]

# 2) extract each page's primary outbound link (first external href that isn't social/infra)
targets=[]
for pid,link,sec,name in reviews:
    try:
        html=wp('/wp-json/wp/v2/pages/%d?context=edit&_fields=content'%pid)['content']['raw']
        primary=None
        for u in re.findall(r'href="(https?://[^"]+)"',html):
            if is_skip(urlparse(u).netloc): continue
            primary=u; break
        targets.append((pid,link,sec,name,primary))
    except Exception as e:
        targets.append((pid,link,sec,name,None)); print('read-fail',pid,e)

# 3) health-check each outbound link
def check(url):
    for attempt in (1,2):                       # retry once on a transient connection error
        try:
            r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=20)
            return r.getcode(), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, url
        except Exception as e:
            if attempt==2: return 'ERR', type(e).__name__
            time.sleep(2)

DEAD={404,410,400,'ERR'}                 # high-confidence broken/closed
SUSPECT={401,403,408,429,500,502,503,504} # alive-but-blocked or flaky -> verify by hand
dead=[]; suspect=[]; moved=[]; missing=[]; ok=0
for pid,link,sec,name,url in targets:
    if not url: missing.append((sec,name,link)); continue
    code,final=check(url); time.sleep(0.25)
    if code in DEAD:
        dead.append((sec,name,url,code,link))
    elif code in SUSPECT:
        suspect.append((sec,name,url,code,link))
    else:
        ok+=1
        d0=urlparse(url).netloc.replace('www.',''); d1=urlparse(final).netloc.replace('www.','') if isinstance(final,str) and final.startswith('http') else ''
        if d1 and d0 not in d1 and d1 not in d0:
            moved.append((sec,name,d0,d1,link))

# 4) report
print('Pearl Watcher: %d review pages | %d healthy | DEAD %d | suspect %d | moved %d | no-link %d'
      %(len(targets),ok,len(dead),len(suspect),len(moved),len(missing)))
def fmt(rows,head,emoji):
    if not rows: return ''
    out=['%s *%s* (%d):'%(emoji,head,len(rows))]
    for r in rows[:20]:
        if head=='Domain moved': out.append('• %s/%s: %s → %s  <%s>'%(r[0],r[1],r[2],r[3],r[4]))
        elif head=='No outbound link': out.append('• %s/%s  <%s>'%(r[0],r[1],r[2]))
        else: out.append('• %s/%s — %s (%s)  <%s>'%(r[0],r[1],r[3],r[2],r[4]))
    return '\n'.join(out)
blocks=[b for b in [fmt(dead,'Dead / closed','🔴'),fmt(missing,'No outbound link','⚫'),
        fmt(suspect,'Blocked or flaky — verify','🟠'),fmt(moved,'Domain moved','🟡')] if b]
for b in blocks: print('\n'+b)

if SLACK and blocks:
    msg='*🛰 Pearl Watcher — %d issues across %d review pages*\n\n'%(len(dead)+len(missing)+len(suspect)+len(moved),len(targets))+'\n\n'.join(blocks)
    try:
        urllib.request.urlopen(urllib.request.Request(SLACK,data=json.dumps({'text':msg[:3500]}).encode(),
            headers={'content-type':'application/json'},method='POST'),timeout=15).read()
        print('\n-> posted to Slack')
    except Exception as e: print('slack skip',e)
elif SLACK:
    try:
        urllib.request.urlopen(urllib.request.Request(SLACK,data=json.dumps({'text':'🛰 Pearl Watcher: all %d outbound links healthy.'%len(targets)}).encode(),
            headers={'content-type':'application/json'},method='POST'),timeout=15).read()
    except Exception as e: print('slack skip',e)
