# PIPEDREAM PYTHON CODE STEP - paste into the "Daily Bias" workflow's `code` step (replace all).
# Two jobs in one write to page 445:
#   (A) The desk read  -> zone daily-brief-read : 6 contracts (ES/NQ/GC/CL/6E/BTC), market-context
#       banner + premium cards (driver + levels rail + technical/fundamental read + "Bias flips if").
#   (B) Event-risk radar -> zone week-ahead : forward-looking high-impact US releases, auto-hides.
# Conditional/level-based read - never live price, never a signal. Free data (Yahoo). No data store.
# Env vars: ANTHROPIC_API_KEY, ANTHROPIC_MODEL, WP_BASE, WP_USER, WP_APP_PASS.

def handler(pd: "pipedream"):
    import urllib.request, json, html, os, base64, re
    from datetime import datetime, date, timedelta, timezone, tzinfo
    KEY=os.environ["ANTHROPIC_API_KEY"]; MODEL=os.environ.get("ANTHROPIC_MODEL","claude-haiku-4-5-20251001")
    BASE=os.environ["WP_BASE"]; AUTH="Basic "+base64.b64encode(("%s:%s"%(os.environ["WP_USER"],os.environ["WP_APP_PASS"])).encode()).decode()
    WPH={'Authorization':AUTH,'User-Agent':'Mozilla/5.0'}

    # ---- US Eastern with DST, no tzdata needed ----
    def _nth_sun(y,mo,n):
        d=date(y,mo,1); d+=timedelta((6-d.weekday())%7); return d+timedelta(7*(n-1))
    class _ET(tzinfo):
        def utcoffset(self,dt):
            dd=dt.date(); h=-4 if _nth_sun(dt.year,3,2)<=dd<_nth_sun(dt.year,11,1) else -5
            return timedelta(hours=h)
        def tzname(self,dt): return 'ET'
        def dst(self,dt): return timedelta(0)
    ET=_ET()

    def pull(sym,interval,rng):
        u='https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s'%(sym,rng,interval)
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read())
        return d['chart']['result'][0]['indicators']['quote'][0]
    def pullq(sym,interval,rng):
        u='https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s'%(sym,rng,interval)
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read())
        r=d['chart']['result'][0]; return r['indicators']['quote'][0], (r.get('timestamp') or [])
    def novwapnum(s):
        # safety net: never let a VWAP price number through (anchor/feed dependent -> would be wrong)
        s=re.sub(r'[\$]?\d[\d,]*(?:\.\d+)?\s*(?:area\s*)?(?=VWAP\b)','',s)
        s=re.sub(r'\bVWAP\b(\s*(?:at|near|around|of|@))?\s*[\$]?\d[\d,]*(?:\.\d+)?','VWAP',s)
        return s
    def ema(a,p):
        k=2/(p+1); e=a[0]; out=[e]
        for x in a[1:]: e=x*k+e*(1-k); out.append(e)
        return out
    def f(x,dp): return ('%.'+str(dp)+'f')%x

    # ================= (A) THE DESK READ =================
    CON=[('ES','S&P 500','ES=F','/markets/es-futures/',0),('NQ','Nasdaq 100','NQ=F','/markets/nq-futures/',0),
         ('GC','Gold','GC=F','/markets/gold-futures/',1),('CL','Crude (WTI)','CL=F','/markets/crude-oil-futures/',2),
         ('6E','Euro FX','6E=F','/markets/euro-fx-futures/',4),('BTC','Bitcoin','BTC=F','/markets/bitcoin-futures/',0)]
    # session VWAP anchor: most recent 18:00 ET futures session open (TradingView's default anchor)
    _nE=datetime.now(ET); _an=_nE.replace(hour=18,minute=0,second=0,microsecond=0)
    if _nE.hour<18: _an=_an-timedelta(days=1)
    VANCH=_an.timestamp()
    rows=[]
    for sym,sub,yf,href,dp in CON:
        try:
            q=pull(yf,'60m','5d'); cl=[c for c in q['close'] if c is not None]
            if len(cl)<26: continue
            qd=pull(yf,'1d','5d'); H=qd['high'][-2]; L=qd['low'][-2]; C=qd['close'][-2]; pp=(H+L+C)/3
            macd=[a-b for a,b in zip(ema(cl,12),ema(cl,26))]; sig=ema(macd,9)
            mom='positive' if macd[-1]>sig[-1] else 'negative'; trend='higher' if cl[-1]>cl[-14] else 'lower'
            q2,ts2=pullq(yf,'30m','5d'); tp=0; vv=0
            for i in range(len(ts2)):
                t=ts2[i]
                if t is None or t<VANCH: continue
                try:
                    cc=q2['close'][i]; vv2=q2['volume'][i]; hi=q2['high'][i]; lo=q2['low'][i]
                    if cc and vv2 and hi is not None and lo is not None:
                        tp+=((hi+lo+cc)/3)*vv2; vv+=vv2
                except: pass
            vwap=(tp/vv) if vv else pp
            vstate='below' if cl[-1]<vwap else 'above'   # published as STATE only, never the number
            rows.append(dict(sym=sym,sub=sub,href=href,dp=dp,pp=pp,H=H,L=L,vwap=vwap,vstate=vstate,mom=mom,trend=trend,last=cl[-1],prev=C))
        except Exception as e: print('skip',sym,e)

    hU=datetime.now(timezone.utc).hour
    SESS=('Asia session' if (hU>=22 or hU<7) else 'London session' if hU<12 else 'NY morning' if hU<16 else 'NY afternoon')
    read_inner=None
    if rows:
        items=[{'symbol':r['sym'],'pivot':f(r['pp'],r['dp']),'resistance':f(r['H'],r['dp']),'support':f(r['L'],r['dp']),
                'vs_session_VWAP':'price is currently %s session VWAP'%r['vstate'],'1h_MACD':r['mom'],'1h_structure':'making %s highs/lows'%r['trend']} for r in rows]
        SYS=('You are the Pearl of Trades futures desk writing the %s read across the desk (ES, NQ, gold, crude, euro, bitcoin). '
         'You blend FUNDAMENTAL drivers with the TECHNICAL picture (fixed daily pivot/resistance/support WITH numbers, plus a session-VWAP STATE, 1h MACD, 1h structure). '
         'CRITICAL: conditional rules around the FIXED numeric levels (pivot/support/resistance) only - never the live price or "X points away". '
         'VWAP RULE: you are told only whether price is ABOVE or BELOW session VWAP. Refer to VWAP ONLY as "above VWAP"/"below VWAP" - NEVER write a VWAP price number (it is anchor- and feed-dependent and would be wrong on the trader chart).\n'
         'Return STRICT JSON {"market_context":"...","items":[{"symbol","direction","driver","read","flip"}]}:\n'
         '- market_context: 2 sentences on the macro backdrop driving the whole desk today (the fundamental picture).\n'
         '- direction: "Bullish lean" | "Bearish lean" | "Neutral".\n'
         '- driver: 3-7 word fundamental driver (e.g. "rising yields after a strong jobs report").\n'
         '- read: 1-2 sentences BLENDING the fundamental driver with the technical levels, as conditional rules (e.g. "Hot jobs lifted yields; while it holds below the 7450 pivot and VWAP, sellers stay in control into 7591.").\n'
         '- flip: PLAIN ENGLISH of what would flip the bias - no jargon (e.g. "A hold back above the 7450 pivot would turn the lean neutral-to-up."). Do NOT use the word invalidation.\n'
         'Output JSON only.')%SESS
        body=json.dumps({'model':MODEL,'max_tokens':2400,'system':SYS,'messages':[{'role':'user','content':json.dumps({'items':items})}]}).encode()
        rq=urllib.request.Request('https://api.anthropic.com/v1/messages',data=body,headers={'x-api-key':KEY,'anthropic-version':'2023-06-01','content-type':'application/json'})
        raw=json.loads(urllib.request.urlopen(rq,timeout=70).read())['content'][0]['text']; raw=raw[raw.find('{'):raw.rfind('}')+1]
        parsed=json.loads(raw); CTX=parsed.get('market_context',''); R={x['symbol']:x for x in parsed['items']}

        CFG={'Bullish':('#16A34A','#ECFDF3','&#9650;'),'Bearish':('#DC2626','#FEF2F2','&#9660;'),'Neutral':('#B45309','#FEF6E7','&#9679;')}
        def card(r):
            x=R.get(r['sym'],{}); dn=x.get('direction','Neutral'); col,bg,ar=CFG.get(dn.split()[0],CFG['Neutral'])
            def Lc(lbl,val): return '<span style="white-space:nowrap;"><span style="color:#9AA6B6;">%s</span> <b style="color:#0B1F3A;">%s</b></span>'%(lbl,val)
            vchip=('&#9660;&nbsp;below' if r['vstate']=='below' else '&#9650;&nbsp;above')
            rail=' &nbsp;&middot;&nbsp; '.join([Lc('S',f(r['L'],r['dp'])),Lc('Pivot',f(r['pp'],r['dp'])),Lc('R',f(r['H'],r['dp'])),Lc('VWAP',vchip)])
            return ('<div style="border:1px solid #E7EBF1;border-radius:14px;background:#fff;overflow:hidden;box-shadow:0 12px 30px rgba(7,26,47,.06);">'
              '<div style="height:4px;background:%s;"></div>'
              '<div style="padding:17px;display:flex;flex-direction:column;gap:11px;">'
                '<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;"><div><span style="font-size:17px;font-weight:950;color:#0B1F3A;">%s</span> <span style="color:#8A94A6;font-size:12.5px;font-weight:600;">%s</span></div>'
                '<span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.03em;color:%s;background:%s;padding:5px 12px;border-radius:999px;">%s %s</span></div>'
                '<div style="font-size:12px;color:#52607A;"><span style="color:#8A5F08;font-weight:800;text-transform:uppercase;letter-spacing:.03em;font-size:10.5px;">Driver</span> &nbsp;%s</div>'
                '<div style="font-size:12.5px;color:#42526E;padding:9px 12px;background:#F6F8FB;border-radius:9px;display:flex;flex-wrap:wrap;gap:4px 0;">%s</div>'
                '<div style="font-size:14px;color:#2A3950;line-height:1.6;">%s</div>'
                '<div style="font-size:12.5px;color:#42526E;background:%s;border-radius:9px;padding:9px 12px;line-height:1.55;"><span style="font-weight:900;color:%s;">&#9873; Bias flips if &middot;</span> %s</div>'
              '</div></div>')%(col,r['sym'],r['sub'],col,bg,ar,dn.replace(' lean',''),html.escape(x.get('driver','')),rail,html.escape(novwapnum(x.get('read',''))),bg,col,html.escape(novwapnum(x.get('flip',''))))

        nowET=datetime.now(ET); stamp='%s, %d:%02d ET'%(nowET.strftime('%b %d'),(nowET.hour%12) or 12,nowET.minute)
        ctxb=('<div style="grid-column:1/-1;padding:17px 19px;border-radius:13px;background:linear-gradient(135deg,#0B1F3A,#16315A);box-shadow:0 14px 34px rgba(7,26,47,.14);">'
         '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px;"><span style="font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.05em;color:#F2C97A;">&#127757; Market context</span>'
         '<span style="font-size:11px;font-weight:800;color:#fff;background:rgba(255,255,255,.12);padding:3px 10px;border-radius:999px;">%s &middot; %s</span>'
         '<span style="font-size:11px;color:#9FB4D0;">updates 4x/day &middot; daily/1h levels, not a live feed</span></div>'
         '<div style="font-size:14.5px;line-height:1.62;color:#EAF1F9;">%s</div></div>')%(SESS,stamp,html.escape(CTX))
        read_inner=ctxb+''.join(card(r) for r in rows)
        # hero live market strip (refreshes the dark hero's glass tiles)
        def fmtc(x,dp):
            s=('%.'+str(dp)+'f')%x
            if dp==0 or x>=1000:
                a,_,b=s.partition('.'); s='{:,}'.format(int(a))+(('.'+b) if b else '')
            return s
        def tile(r):
            chg=((r['last']-r['prev'])/r['prev']*100) if r['prev'] else 0
            cls='up' if chg>=0 else 'dn'; arr='&#9650;' if chg>=0 else '&#9660;'
            return ('<a class="hero-tile" href="%s%s"><div class="ht-sym">%s</div><div class="ht-last">%s</div>'
                    '<div class="ht-chg %s">%s %+.1f%%</div></a>')%(BASE,r['href'],r['sym'],fmtc(r['last'],r['dp']),cls,arr,chg)
        strip_inner=''.join(tile(r) for r in rows)

    # ================= (B) EVENT-RISK RADAR =================
    YEAR=datetime.now(ET).year
    EVENTS=[
     ('CPI','Consumer Price Index','/economic-events/cpi/','HIGH',35,[(6,10),(7,14),(8,12),(9,11),(10,14),(11,10),(12,10)],(8,30)),
     ('Jobs','Nonfarm Payrolls (jobs report)','/economic-events/nfp/','HIGH',35,[(6,5),(7,2),(8,7),(9,4),(10,2),(11,6),(12,4)],(8,30)),
     ('FOMC','Fed rate decision','/economic-events/fomc/','HIGH',50,[(6,17),(7,29),(9,16),(10,28),(12,9)],(14,0)),
     ('PPI','Producer Price Index','/futures-economic-calendar/','MED',21,[(6,11),(7,15),(8,13),(9,10),(10,15),(11,13),(12,15)],(8,30)),
     ('Retail Sales','Retail Sales','/futures-economic-calendar/','MED',21,[(6,17),(7,16),(8,14),(9,16),(10,15),(11,17),(12,16)],(8,30)),
     ('PCE','PCE inflation (Fed gauge)','/futures-economic-calendar/','MED',21,[(6,25),(7,30),(8,26),(9,30),(10,29),(11,25),(12,23)],(8,30)),
     ('Consumer Sentiment','Consumer Sentiment (UMich, prelim)','/futures-economic-calendar/','MED',21,[(6,12),(7,10),(8,14),(9,11),(10,9),(11,13),(12,11)],(10,0)),
    ]
    # LIVE source: FRED releases/dates (free, authoritative, auto-updating) with the fixed table
    # above as fallback. FRED gives the real scheduled date; we supply time + impact + link.
    FRED_MAP={
     'Consumer Price Index':('CPI','Consumer Price Index','/economic-events/cpi/','HIGH',35,(8,30)),
     'Employment Situation':('Jobs','Nonfarm Payrolls (jobs report)','/economic-events/nfp/','HIGH',35,(8,30)),
     'Producer Price Index':('PPI','Producer Price Index','/futures-economic-calendar/','MED',21,(8,30)),
     'Personal Income and Outlays':('PCE','PCE inflation (Fed gauge)','/futures-economic-calendar/','MED',21,(8,30)),
     'Gross Domestic Product':('GDP','Gross Domestic Product','/futures-economic-calendar/','MED',21,(8,30)),
     'Advance Monthly Sales for Retail and Food Services':('Retail Sales','Retail Sales','/futures-economic-calendar/','MED',21,(8,30)),
     'Job Openings and Labor Turnover Survey':('JOLTS','Job Openings (JOLTS)','/futures-economic-calendar/','MED',21,(10,0)),
    }
    SUPP=[  # movers FRED lacks on the right date: FOMC + UMich PRELIM (FRED only has the final)
     ('FOMC','Fed rate decision','/economic-events/fomc/','HIGH',50,[(2026,6,17),(2026,7,29),(2026,9,16),(2026,10,28),(2026,12,9)],(14,0)),
     ('Consumer Sentiment','Consumer Sentiment (UMich, prelim)','/futures-economic-calendar/','MED',21,[(2026,6,12),(2026,7,10),(2026,8,14),(2026,9,11),(2026,10,9),(2026,11,13),(2026,12,11)],(10,0)),
    ]
    def fred_candidates(now,today,key):
        u=('https://api.stlouisfed.org/fred/releases/dates?api_key=%s&file_type=json'
           '&realtime_start=%s&include_release_dates_with_no_data=true&sort_order=asc&limit=1000')%(key,today.isoformat())
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read())
        cc=[]; seen=set()
        for r in d.get('release_dates',[]):
            nm=(r.get('release_name','') or '').strip(); ds=r.get('date','') or ''
            m=FRED_MAP.get(nm)
            if not m: continue
            lbl,full,href,imp,look,(hh,mm)=m
            if lbl in seen: continue
            try: y,mo,dy=map(int,ds.split('-'))
            except: continue
            dt=datetime(y,mo,dy,hh,mm,tzinfo=ET)
            if dt<now: continue
            dd=(dt.date()-today).days
            if dd>look: continue
            cc.append((dt,dd,lbl,full,href,imp)); seen.add(lbl)
        for lbl,full,href,imp,look,dates,(hh,mm) in SUPP:
            for (y,mo,dy) in dates:
                dt=datetime(y,mo,dy,hh,mm,tzinfo=ET)
                if dt<now: continue
                dd=(dt.date()-today).days
                if dd<=look: cc.append((dt,dd,lbl,full,href,imp))
                break
        cc.sort(key=lambda x:x[0]); return cc[:5]
    def table_candidates(now,today):
        last_dt=max(datetime(YEAR,mo,dy,hh,mm,tzinfo=ET) for _,_,_,_,_,ds,(hh,mm) in EVENTS for mo,dy in ds)
        if now>last_dt: return [],True
        cc=[]
        for lbl,full,href,imp,look,ds,(hh,mm) in EVENTS:
            for mo,dy in ds:
                dt=datetime(YEAR,mo,dy,hh,mm,tzinfo=ET)
                if dt<now: continue
                dd=(dt.date()-today).days
                if dd>look: continue
                cc.append((dt,dd,lbl,full,href,imp)); break
        cc.sort(key=lambda x:x[0]); return cc[:5],False
    now=datetime.now(ET); today=now.date()
    FKEY=os.environ.get('FRED_API_KEY',''); STALE=False; cand=[]
    if FKEY:
        try: cand=fred_candidates(now,today,FKEY)
        except Exception as e: print('FRED fetch failed -> table fallback:',e); FKEY=''
    if not FKEY:
        cand,STALE=table_candidates(now,today)
    def when(dt,dd):
        t='%d:%02d ET'%((dt.hour%12) or 12,dt.minute)
        return ('Today &middot; '+t) if dd==0 else ('Tomorrow &middot; '+t) if dd==1 else dt.strftime('%a %b ')+str(dt.day)+' &middot; '+t
    if cand:
        chips=''.join(('<a class="radar-chip %s" href="%s%s" title="%s"><span class="rc-when">%s</span><span class="rc-name">%s</span></a>')
            %(('high' if imp=='HIGH' else 'med'),BASE,href,html.escape(full),when(dt,dd),html.escape(lbl)) for dt,dd,lbl,full,href,imp in cand)
        radar_inner=('<div class="pot-db-wrap"><div class="pot-db-radar">'
          '<span class="radar-label">&#128276; On the radar</span><div class="radar-chips">%s</div>'
          '<span class="radar-note">Scheduled high-impact US data &mdash; dates set by the agencies; expect volatility, size down or stand aside into the print.</span>'
          '</div></div>')%chips
    else:
        radar_inner=''  # nothing ahead or schedule stale -> banner collapses

    # ================= WRITE ALL ZONES IN ONE POST =================
    import re as _re
    def splice(c,name,inner):
        s='<!--ZONE:%s-START-->'%name; e='<!--ZONE:%s-END-->'%name
        i=c.find(s); j=c.find(e)
        return c if (i<0 or j<0) else c[:i+len(s)]+inner+c[j:]
    g=urllib.request.Request(BASE+'/wp-json/wp/v2/pages/445?context=edit',headers=WPH)
    c=json.loads(urllib.request.urlopen(g,timeout=20).read())['content']['raw']
    if read_inner is not None:
        c=splice(c,'daily-brief-read',read_inner)
        c=splice(c,'hero-strip',strip_inner)
        # (C) archive upsert: one row per day, latest direction wins, rolling 12
        DMAP={'Bullish':'long','Bearish':'short','Neutral':'neutral'}; nd=datetime.now(ET)
        d_iso=nd.strftime('%Y-%m-%d'); tags=''
        for s in ['ES','NQ','GC','CL','6E']:
            d=DMAP.get((R.get(s,{}).get('direction','Neutral')).split()[0],'neutral')
            tags+='<i class="at %s">%s %s</i>'%(d,s,d.capitalize())
        row=('<div class="arch-row" data-d="%s"><span class="arch-date">%s</span><span class="arch-tags">%s</span></div>'
             %(d_iso,nd.strftime('%a &middot; %b %d'),tags))
        a=c.find('<!--ZONE:daily-brief-archive-START-->'); b=c.find('<!--ZONE:daily-brief-archive-END-->')
        if a>=0 and b>=0:
            cur=c[a+len('<!--ZONE:daily-brief-archive-START-->'):b]
            ex=[r for r in _re.findall(r'<div class="arch-row"[^>]*>.*?</div>',cur,_re.S) if ('data-d="%s"'%d_iso) not in r]
            c=splice(c,'daily-brief-archive',row+''.join(ex[:11]))
    c=splice(c,'week-ahead',radar_inner)
    p=urllib.request.Request(BASE+'/wp-json/wp/v2/pages/445',data=json.dumps({'content':c}).encode(),
        headers={'Authorization':AUTH,'User-Agent':'Mozilla/5.0','content-type':'application/json'},method='POST')
    urllib.request.urlopen(p,timeout=30).read()
    for url in [BASE+'/wp-json/elementor/v1/cache',BASE+'/wp-admin/admin.php?page=litespeed&action=purge_all']:
        try: urllib.request.urlopen(urllib.request.Request(url,headers=WPH,method='DELETE' if 'elementor' in url else 'GET'),timeout=15).read()
        except: pass
    # optional Slack ping - uses a dedicated bias webhook if set, else the shared news webhook
    hook=os.environ.get('SLACK_BIAS_WEBHOOK_URL') or os.environ.get('SLACK_WEBHOOK_URL')
    if hook and rows:
        AR={'Bullish':'\U0001F7E2','Bearish':'\U0001F534','Neutral':'\U0001F7E1'}
        line=' · '.join('%s %s'%(AR.get((R.get(r['sym'],{}).get('direction','Neutral')).split()[0],'\U0001F7E1'),r['sym']) for r in rows)
        rdr=', '.join(c[2] for c in cand) or 'clear'
        msg=('*Pearl Daily Bias — %s*\n%s\n\U0001F4C5 On the radar: %s\n%s/daily-futures-brief/'%(SESS,line,rdr,BASE))
        try:
            hb=urllib.request.Request(hook,data=json.dumps({'text':msg}).encode(),headers={'content-type':'application/json'},method='POST')
            urllib.request.urlopen(hb,timeout=15).read()
        except Exception as e: print('slack skip',e)
    radar_txt=('STALE - refresh the %d event schedule!'%YEAR) if STALE else (', '.join(c[2] for c in cand) or 'none')
    summary='%sDaily Bias (%s): %d cards | radar: %s'%(('⚠️ ' if STALE else ''),SESS,len(rows),radar_txt)
    print(summary); return summary


if __name__ == "__main__":
    # GitHub Actions / CLI entry point — reads all config from environment variables.
    handler(None)
