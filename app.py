# sportybet_bot.py - V14.2 - STRICT + SAVE ON SERVER + BOOK ALL SAVED - PASTE WHOLE FILE
import sys, json, time, requests, re, os, random, threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import concurrent.futures
from flask import Flask, jsonify, render_template_string, request

LAGOS = ZoneInfo("Africa/Lagos")
UTC = ZoneInfo("UTC")
TARGET_TOTAL_ODD = 8000
FOOTBALL_MAX = 35
BASKETBALL_MAX = 35
DAYS_AHEAD = 7
HISTORY_DAYS = 30
SPORTYBET_NG = "https://www.sportybet.com/ng/"
CACHE_FILE = "last2_cache.json"
SAVED_FILE = "saved_weekend.json"
LAST2_MAP = {}
FAIL = {"skip": {}}

app = Flask(__name__)
STATE = {"running": False, "last_run": None, "error": None, "tickets": None}
STATE_LOCK = threading.Lock()

def log_skip(r): FAIL["skip"][r] = FAIL["skip"].get(r, 0) + 1
def clean(s):
    s = s.lower()
    s = re.sub(r'\b(fc|cf|sc|ac|bk|bc|club|real|atletico|athletic|deportivo)\b', '', s)
    return ' '.join(re.sub(r'[^a-z0-9 ]', '', s).split())
def lagos_now(): return datetime.now(LAGOS)
def parse_espn_time(date_str):
    try:
        if not date_str: return None
        dt_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt_utc.tzinfo is None: dt_utc = dt_utc.replace(tzinfo=UTC)
        return dt_utc.astimezone(LAGOS)
    except: return None

FOOTBALL_LEAGUES = [
    ("soccer", "eng.1", "Premier League"),("soccer", "esp.1", "LaLiga"),("soccer", "ita.1", "Serie A"),
    ("soccer", "ger.1", "Bundesliga"),("soccer", "fra.1", "Ligue 1"),("soccer", "ned.1", "Eredivisie"),
    ("soccer", "por.1", "Liga Portugal"),("soccer", "tur.1", "Super Lig"),("soccer", "eng.2", "Championship"),
    ("soccer", "usa.1", "MLS"),("soccer", "mex.1", "Liga MX"),("soccer", "jpn.1", "J1 League"),
    ("soccer", "kor.1", "K-League 1"),("soccer", "sau.1", "Saudi Pro League"),("soccer", "bra.1", "Brasileiro Serie A"),
    ("soccer", "uefa.champions", "UEFA Champions League"),("soccer", "uefa.europa", "UEFA Europa League"),
    ("soccer", "uefa.conference", "UEFA Conference League"),("soccer", "uefa.nations", "UEFA Nations League"),
    ("soccer", "fifa.friendly", "Int. Friendly Games"),("soccer", "conmebol.libertadores", "CONMEBOL Libertadores"),
    ("soccer", "conmebol.sudamericana", "CONMEBOL Sudamericana"),
]
BASKETBALL_LEAGUES = [("basketball", "nba", "NBA"),("basketball", "mens-college-basketball", "NCAA, Regular Season"),("basketball", "wnba", "WNBA")]
USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36","Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"]
def espn_get(url):
    for attempt in range(3):
        try:
            time.sleep(0.35 + random.uniform(0, 0.2))
            r = requests.get(url, timeout=20, headers={"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"})
            if r.status_code == 429: time.sleep(2*(attempt+1)); continue
            if r.status_code in (400, 404): return None
            if r.status_code != 200: return None
            return r.json()
        except: time.sleep(2*(attempt+1))
    return None
def fetch_sb(sport, league, date_str=None):
    base = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
    url = base + (f"?dates={date_str}" if date_str else "")
    data = espn_get(url)
    return data.get("events", []) if data else []
def load_cache():
    global LAST2_MAP
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f: LAST2_MAP = json.load(f)
        except: LAST2_MAP = {}
def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(LAST2_MAP, f)
    except: pass
def build_last2(sport, league, days=HISTORY_DAYS):
    prefix = f"{sport}-{league}-"
    if any(k.startswith(prefix) for k in LAST2_MAP): return
    today = lagos_now()
    for d in range(1, days+1):
        dt = today - timedelta(days=d); ds = dt.strftime("%Y%m%d")
        for ev in fetch_sb(sport, league, ds):
            try:
                comp = ev.get("competitions", [{}])[0]
                if comp.get("status", {}).get("type", {}).get("state", "") not in ("post", "final", "full", "", None): continue
                teams = comp.get("competitors", [])
                if len(teams) < 2: continue
                t0, t1 = teams[0], teams[1]; s0, s1 = t0.get("score"), t1.get("score")
                if s0 is None or s1 is None: continue
                s0, s1 = int(float(s0)), int(float(s1))
                for mine, opp, my, op in [(t0, t1, s0, s1), (t1, t0, s1, s0)]:
                    k = f"{sport}-{league}-{mine['team']['id']}"
                    LAST2_MAP.setdefault(k, []); e = [ds, my, op, str(opp["team"]["displayName"])]
                    if e not in LAST2_MAP[k]: LAST2_MAP[k].append(e)
            except: continue
    for k in list(LAST2_MAP):
        if k.startswith(prefix): LAST2_MAP[k] = sorted(LAST2_MAP[k], reverse=True)[:2]
def get_last2(sport, league, tid):
    lst = LAST2_MAP.get(f"{sport}-{league}-{tid}", [])
    if len(lst) < 2:
        log_skip("last2_lt2_strict_skip"); return None
    scored = [x[1] for x in lst]; conceded = [x[2] for x in lst]
    avg_s = sum(scored)/2; avg_c = sum(conceded)/2; speed = scored[0]-scored[1]
    wins = sum(1 for my, op in zip(scored, conceded) if my > op)
    if sport == "soccer": attack = round(avg_s*2, 1); defence = round(max(0, 5-avg_c), 1)
    else: attack = round(avg_s/10, 1); defence = round(max(0, 10-avg_c/10), 1)
    return {"games": 2, "scored": scored, "conceded": conceded, "avg_scored": round(avg_s,2), "avg_conceded": round(avg_c,2), "total": round(avg_s+avg_c,1), "wins": wins, "speed": speed, "attack": attack, "defence": defence}
def fetch_next_7_days(sport, league):
    out=[]; now_lagos=lagos_now(); today=now_lagos
    for offset in range(DAYS_AHEAD):
        dt_day=today+timedelta(days=offset); ds=dt_day.strftime("%Y%m%d")
        for ev in fetch_sb(sport, league, ds):
            try:
                comp=ev.get("competitions", [{}])[0]; state=comp.get("status", {}).get("type", {}).get("state", "")
                if state in ("post","final","full","in") and offset==0: continue
                teams=comp.get("competitors", [])
                if len(teams)<2: continue
                h=next((t for t in teams if t.get("homeAway")=="home"),None); a=next((t for t in teams if t.get("homeAway")=="away"),None)
                if not h or not a: continue
                kickoff_lagos=parse_espn_time(ev.get("date",""))
                if kickoff_lagos is None: kickoff_lagos=dt_day.replace(hour=12,minute=0)
                if kickoff_lagos < now_lagos: continue
                date_label=kickoff_lagos.strftime("%Y-%m-%d"); time_label=kickoff_lagos.strftime("%H:%M")
                days_from_now=(kickoff_lagos.date()-now_lagos.date()).days
                bookable="BOOK NOW" if days_from_now<=2 else "WAIT - WEEKEND"
                out.append({"home": h["team"]["displayName"], "away": a["team"]["displayName"], "home_id": str(h["team"]["id"]), "away_id": str(a["team"]["id"]), "league": league, "sport": sport, "date": date_label, "time": time_label, "days_from_now": days_from_now, "bookable": bookable})
            except: continue
    return out
def analyse_football(g, hs, aws):
    h_pow=hs["attack"]+hs["defence"]+hs["wins"]*1.5+max(0,hs["speed"])*0.5; a_pow=aws["attack"]+aws["defence"]+aws["wins"]*1.5+max(0,aws["speed"])*0.5
    gap=h_pow-a_pow; combined=round((hs["total"]+aws["total"])/2,2)
    base={"home": g["home"], "away": g["away"], "league": g["league"], "date": g["date"], "time": g.get("time",""), "days_from_now": g.get("days_from_now",0), "bookable": g.get("bookable","")}
    if abs(gap) >= 2.0:
        if gap>0: return {**base, "market": "1 - Home Win", "est_odd": round(1.85+min(0.9,abs(gap)*0.08),2), "reason": f"HOME STRICT | H {hs['scored']} vs A {aws['scored']} Gap {round(gap,1)}", "score": abs(gap)}
        else: return {**base, "market": "2 - Away Win", "est_odd": round(1.95+min(0.9,abs(gap)*0.08),2), "reason": f"AWAY STRICT | A {aws['scored']} vs H {hs['scored']} Gap {round(gap,1)}", "score": abs(gap)}
    if combined>=2.6 and hs["avg_scored"]>=1.2 and aws["avg_scored"]>=1.2:
        line="Over 3.5" if combined>=3.8 else "Over 2.5"; odd=2.10 if line=="Over 3.5" else 1.75
        return {**base, "market": line, "est_odd": odd, "reason": f"OVER {line} STRICT | Combined {combined}", "score": combined}
    if combined<=2.2 and hs["avg_scored"]<=1.3 and aws["avg_scored"]<=1.3:
        return {**base, "market": "Under 2.5", "est_odd": 1.80, "reason": f"UNDER 2.5 STRICT | Combined {combined}", "score": 3.0-combined}
    log_skip("football_no_edge_strict"); return None
def analyse_basketball(g, hs, aws):
    h_pow=hs["avg_scored"]-hs["avg_conceded"]+hs["wins"]*5+hs["speed"]; a_pow=aws["avg_scored"]-aws["avg_conceded"]+aws["wins"]*5+aws["speed"]
    gap=h_pow-a_pow; expected=round((hs["total"]+aws["total"])/2,1)
    base={"home": g["home"], "away": g["away"], "league": g["league"], "date": g["date"], "time": g.get("time",""), "days_from_now": g.get("days_from_now",0), "bookable": g.get("bookable","")}
    if abs(gap) >= 8:
        if gap>0: return {**base, "market": "1 - Home Win", "est_odd": 1.85, "reason": f"HOME WIN STRICT | H {hs['scored']} vs A {aws['scored']} Gap {round(gap,1)}", "score": abs(gap)}
        else: return {**base, "market": "2 - Away Win", "est_odd": 1.95, "reason": f"AWAY WIN STRICT | A {aws['scored']} vs H {hs['scored']} Gap {round(gap,1)}", "score": abs(gap)}
    comfort=min(hs["total"], aws["total"]); line=float(int(comfort*2)/2)
    if expected>line+5: return {**base, "market": f"Over {line}", "est_odd": 1.85, "reason": f"OVER {line} STRICT | Expected {expected}", "score": expected, "lowest_line": line}
    if expected<line-5: return {**base, "market": f"Under {line}", "est_odd": 1.85, "reason": f"UNDER {line} STRICT | Expected {expected}", "score": 100-expected, "lowest_line": line}
    log_skip("basket_no_edge_strict"); return None
def build_ticket(candidates, max_games):
    candidates=sorted(candidates, key=lambda x: x["score"], reverse=True); picked=[]; total=1.0
    for c in candidates:
        if len(picked)>=max_games: break
        picked.append(c); total*=c["est_odd"]
        if total>=TARGET_TOTAL_ODD and len(picked)>=12: break
    return picked, round(total,1)
def build_all_last2(leagues):
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(build_last2, s, l, HISTORY_DAYS): (s,l,n) for s,l,n in leagues}
        for f in concurrent.futures.as_completed(futs):
            try: f.result()
            except: pass
    save_cache()
def fetch_all_7days(leagues):
    all_games=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(fetch_next_7_days, s, l): (s,l,n) for s,l,n in leagues}
        for f in concurrent.futures.as_completed(futs):
            s,l,n=futs[f]
            try:
                gs=f.result()
                for g in gs: g["league_name"]=n
                all_games.extend(gs)
            except: pass
    seen=set(); uniq=[]
    for g in all_games:
        k=(clean(g["home"]), clean(g["away"]), g["date"], g.get("time",""))
        if k not in seen: seen.add(k); uniq.append(g)
    return uniq
def run_picker():
    now=lagos_now(); load_cache()
    build_all_last2(FOOTBALL_LEAGUES); f_games=fetch_all_7days(FOOTBALL_LEAGUES)
    f_now_cands=[]; f_weekend_cands=[]
    for g in f_games:
        hs=get_last2(g["sport"], g["league"], g["home_id"]); aws=get_last2(g["sport"], g["league"], g["away_id"])
        if not hs or not aws: continue
        p=analyse_football(g, hs, aws)
        if p:
            p["league_name"]=g.get("league_name", g["league"])
            if g.get("days_from_now",99)<=2: f_now_cands.append(p)
            else: f_weekend_cands.append(p)
    f_now_ticket, f_now_total=build_ticket(f_now_cands, FOOTBALL_MAX); f_weekend_ticket, f_weekend_total=build_ticket(f_weekend_cands, FOOTBALL_MAX)
    build_all_last2(BASKETBALL_LEAGUES); b_games=fetch_all_7days(BASKETBALL_LEAGUES)
    b_now_cands=[]; b_weekend_cands=[]
    for g in b_games:
        hs=get_last2(g["sport"], g["league"], g["home_id"]); aws=get_last2(g["sport"], g["league"], g["away_id"])
        if not hs or not aws: continue
        p=analyse_basketball(g, hs, aws)
        if p:
            p["league_name"]=g.get("league_name", g["league"])
            if g.get("days_from_now",99)<=2: b_now_cands.append(p)
            else: b_weekend_cands.append(p)
    b_now_ticket, b_now_total=build_ticket(b_now_cands, BASKETBALL_MAX); b_weekend_ticket, b_weekend_total=build_ticket(b_weekend_cands, BASKETBALL_MAX)
    tickets={"football_book_now": f_now_ticket, "football_book_now_total": f_now_total, "football_weekend": f_weekend_ticket, "football_weekend_total": f_weekend_total, "basketball_book_now": b_now_ticket, "basketball_book_now_total": b_now_total, "basketball_weekend": b_weekend_ticket, "basketball_weekend_total": b_weekend_total, "generated_at_lagos": now.isoformat(), "skips": FAIL["skip"]}
    with open("tickets.json","w",encoding="utf-8") as f: json.dump(tickets,f,indent=2,ensure_ascii=False)
    with STATE_LOCK: STATE["tickets"] = tickets
    return tickets
def _run_in_background():
    with STATE_LOCK: STATE["running"] = True; STATE["error"] = None
    try:
        run_picker()
        with STATE_LOCK: STATE["last_run"] = lagos_now().isoformat()
    except Exception as e:
        with STATE_LOCK: STATE["error"] = str(e)
    finally:
        with STATE_LOCK: STATE["running"] = False

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SportyBot V14 - STRICT</title>
<style>body{font-family:Arial,sans-serif;background:#0f1115;color:#fff;margin:0;padding:16px}h1{font-size:22px}button{background:#00c853;color:#fff;border:0;padding:14px 20px;font-size:18px;border-radius:10px;width:100%;cursor:pointer;margin-top:10px}button:disabled{opacity:.5}.save{background:#ff9800;color:#000}.view{background:#2196f3}.bookall{background:#7c4dff}.card{background:#1c1f26;padding:14px;border-radius:12px;margin-top:14px}.game{border-bottom:1px solid #333;padding:8px 0}.tag{background:#ff9800;color:#000;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:bold}.muted{color:#aaa}.book{display:block;background:#00c853;color:#fff;text-align:center;padding:12px;border-radius:8px;margin-top:8px;text-decoration:none;font-weight:bold}.savedbox{border:2px solid #ff9800;padding:10px;border-radius:10px}</style></head>
<body><h1>⚽ SportyBot V14 - STRICT</h1><p class="muted">Last 2 in 30 days | STRICT 2 games or SKIP | Lagos time | Target 8000</p>
<button id="runBtn" onclick="runPick()">▶ RUN PICK NOW</button>
<button class="save" onclick="saveWeekend()">💾 SAVE WEEKEND TICKET - Keep this exact ticket</button>
<button class="view" onclick="viewSaved()">📂 VIEW SAVED TICKET</button>
<button class="bookall" onclick="bookAllSaved()">🎯 BOOK ALL SAVED WEEKEND - Open all games on SportyBet</button>
<p id="status" class="muted">Weekend ticket WILL change if you re-run. SAVE it now, then book it later from SAVED.</p>
<div id="out"></div>
<script>
let CURRENT=null; let SAVED=null;
async function runPick(){document.getElementById('runBtn').disabled=true;document.getElementById('status').innerText='Running... please wait 1-3 mins, do not close...';
let r=await fetch('/run',{method:'POST'});
let t=setInterval(async()=>{let s=await (await fetch('/status')).json();document.getElementById('status').innerText=s.running?'Still running...':'Done! '+ (s.last_run||'');
if(!s.running){clearInterval(t);document.getElementById('runBtn').disabled=false;load();}},3000);}
function bookLink(g){let q=encodeURIComponent(g.home+' vs '+g.away);return '<a class="book" href="https://www.sportybet.com/ng/search?query='+q+'" target="_blank">➡️ BOOK THIS GAME ON SPORTYBET</a>';}
function render(t, titlePrefix, isSaved){let html='';function sec(title,list,total){let h='<div class="card"><h3>'+title+' - '+list.length+' games | TOTAL ~'+total+'</h3>';if(!list.length)h+='<p>No strict picks. SKIP is good.</p>';list.forEach((g,i)=>{h+='<div class="game"><b>'+(i+1)+'. '+g.home+' vs '+g.away+'</b><br>'+g.league_name+' | '+g.date+' '+g.time+' Lagos <span class="tag">'+g.bookable+'</span><br>'+g.market+' @ '+g.est_odd+'<br><span class="muted">'+g.reason+'</span><br>'+bookLink(g)+'</div>'});h+='</div>';return h;}
html+=sec(titlePrefix+' FOOTBALL BOOK NOW',t.football_book_now||[],t.football_book_now_total||0);html+=sec(titlePrefix+' FOOTBALL WEEKEND',t.football_weekend||[],t.football_weekend_total||0);html+=sec(titlePrefix+' BASKETBALL BOOK NOW',t.basketball_book_now||[],t.basketball_book_now_total||0);html+=sec(titlePrefix+' BASKETBALL WEEKEND',t.basketball_weekend||[],t.basketball_weekend_total||0);
html+='<div class="card muted">Generated: '+t.generated_at_lagos+'</div>';return html;}
async function load(){let d=await (await fetch('/api/tickets')).json();let el=document.getElementById('out');if(!d||!d.tickets){el.innerHTML='<p>No picks yet. Press RUN PICK NOW.</p>';return;}CURRENT=d.tickets;el.innerHTML=render(CURRENT,'',false);checkSavedBadge();}
async function checkSavedBadge(){let s=await (await fetch('/saved')).json();if(s&&s.saved){SAVED=s.saved;document.getElementById('status').innerText='✅ You have a SAVED weekend ticket from '+s.saved.saved_at+' - Tap VIEW SAVED to book it.';}}
async function saveWeekend(){if(!CURRENT){alert('Run pick first, then save.');return;}
let saved={saved_at:new Date().toISOString(), football_weekend:CURRENT.football_weekend, football_weekend_total:CURRENT.football_weekend_total, basketball_weekend:CURRENT.basketball_weekend, basketball_weekend_total:CURRENT.basketball_weekend_total, generated_at_lagos:CURRENT.generated_at_lagos};
let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(saved)});let j=await r.json();
if(j.ok){SAVED=saved;localStorage.setItem('saved_weekend_ticket',JSON.stringify(saved));alert('✅ WEEKEND TICKET SAVED ON SERVER!\\nFootball Weekend: '+saved.football_weekend.length+' games TOTAL ~'+saved.football_weekend_total+'\\nIt will NOT change even if you re-run. Book it later from VIEW SAVED.');}
else alert('Save failed, try again.');}
async function viewSaved(){let s=await (await fetch('/saved')).json();if(!s||!s.saved){let ls=localStorage.getItem('saved_weekend_ticket');if(!ls){alert('No saved ticket yet. Run pick then tap SAVE WEEKEND TICKET.');return;}s={saved:JSON.parse(ls)};}
SAVED=s.saved;let t=s.saved;let full={football_book_now:[],football_book_now_total:0,football_weekend:t.football_weekend,football_weekend_total:t.football_weekend_total,basketball_book_now:[],basketball_book_now_total:0,basketball_weekend:t.basketball_weekend,basketball_weekend_total:t.basketball_weekend_total,generated_at_lagos:t.generated_at_lagos+' (SAVED AT '+t.saved_at+' - WILL NOT CHANGE)'};
document.getElementById('out').innerHTML='<div class="savedbox"><h2>📂 SAVED WEEKEND TICKET - This will NOT change</h2><p class="muted">This is your exact saved ticket. Tap BOOK on any game, or BOOK ALL below.</p><button class="bookall" onclick="bookAllSaved()">🎯 BOOK ALL SAVED WEEKEND NOW</button></div>'+render(full,'SAVED',true);}
async function bookAllSaved(){if(!SAVED){let s=await (await fetch('/saved')).json();if(!s||!s.saved){alert('No saved ticket. Save weekend first.');return;}SAVED=s.saved;}
let all=[...SAVED.football_weekend, ...SAVED.basketball_weekend];if(!all.length){alert('Saved ticket is empty.');return;}
if(!confirm('Open '+all.length+' games on SportyBet one by one?\\nChrome may block popups - allow popups for this site, then tap again.\\n\\nYou will tap the odd for each game yourself.'))return;
all.forEach((g,i)=>{setTimeout(()=>{let q=encodeURIComponent(g.home+' vs '+g.away);window.open('https://www.sportybet.com/ng/search?query='+q,'_blank');}, i*1200);});
alert('Opening '+all.length+' games... Wait for tabs to open, log in to SportyBet website in Chrome if asked, then tap the odd for each game.');}
load();
</script></body></html>
"""

@app.route("/")
def home(): return render_template_string(HTML)
@app.route("/status")
def status():
    with STATE_LOCK: return jsonify({"running": STATE["running"], "last_run": STATE["last_run"], "error": STATE["error"]})
@app.route("/api/tickets")
def api_tickets():
    with STATE_LOCK:
        if STATE["tickets"]: return jsonify({"tickets": STATE["tickets"]})
    try:
        with open("tickets.json", encoding="utf-8") as f: return jsonify({"tickets": json.load(f)})
    except: return jsonify({"tickets": None})
@app.route("/run", methods=["POST"])
def run():
    with STATE_LOCK:
        if STATE["running"]: return jsonify({"ok": False, "msg": "Already running"})
    th = threading.Thread(target=_run_in_background, daemon=True); th.start()
    return jsonify({"ok": True, "msg": "Started"})
@app.route("/save", methods=["POST"])
def save_weekend():
    try:
        data = request.get_json(force=True)
        data["saved_at"] = data.get("saved_at") or lagos_now().isoformat()
        with open(SAVED_FILE,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e: return jsonify({"ok": False, "error": str(e)})
@app.route("/saved")
def get_saved():
    try:
        with open(SAVED_FILE, encoding="utf-8") as f: return jsonify({"saved": json.load(f)})
    except: return jsonify({"saved": None})
@app.route("/health")
def health(): return jsonify({"ok": True})
if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "--web"
    if mode=="--pick": run_picker()
    else:
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
