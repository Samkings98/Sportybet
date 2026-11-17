
# sportybet_bot.py - V13.4 COMPLETE - STRICT - PASTE WHOLE FILE
# Lagos time | Last 2 in 30 days, STRICT 2 games or SKIP | No weak picks | BOOK NOW + WEEKEND
# python sportybet_bot.py --pick
import sys, json, time, requests, re, math, os, random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import concurrent.futures

LAGOS = ZoneInfo("Africa/Lagos")
UTC = ZoneInfo("UTC")
TARGET_TOTAL_ODD = 8000
FOOTBALL_MAX = 35
BASKETBALL_MAX = 35
DAYS_AHEAD = 7
HISTORY_DAYS = 30  # STRICT: 30 days to find 2 real games. If not found in 30 days -> SKIP.
STAKE = 1000
DRY_RUN = True
SPORTYBET_NG = "https://www.sportybet.com/ng/"
CACHE_FILE = "last2_cache.json"
LAST2_MAP = {}
FAIL = {"skip": {}}

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
            print(f"Loaded Last2 cache: {len(LAST2_MAP)} teams")
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

# STRICT: Must have 2 REAL games. No 1-game duplicate. No cross-league name fallback.
def get_last2(sport, league, tid):
    lst = LAST2_MAP.get(f"{sport}-{league}-{tid}", [])
    if len(lst) < 2:
        log_skip("last2_lt2_strict_skip")
        return None
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

# STRICT: No relaxed param. Same thresholds for BOOK NOW and WEEKEND.
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
    # NO Over 1.5 filler - if it doesn't pass above, SKIP. Strict.
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
    # NO relaxed filler - SKIP if no strict edge
    log_skip("basket_no_edge_strict"); return None

def build_ticket(candidates, max_games):
    candidates=sorted(candidates, key=lambda x: x["score"], reverse=True); picked=[]; total=1.0
    for c in candidates:
        if len(picked)>=max_games: break
        picked.append(c); total*=c["est_odd"]
        if total>=TARGET_TOTAL_ODD and len(picked)>=12: break
    return picked, round(total,1)
def build_all_last2(leagues):
    print(f"Building Last2 for {len(leagues)} leagues (30 days STRICT history)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(build_last2, s, l, HISTORY_DAYS): (s,l,n) for s,l,n in leagues}
        for f in concurrent.futures.as_completed(futs):
            try: f.result()
            except Exception as e: print(f"  Fail: {e}")
    save_cache(); print("  Done")
def fetch_all_7days(leagues):
    all_games=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(fetch_next_7_days, s, l): (s,l,n) for s,l,n in leagues}
        for f in concurrent.futures.as_completed(futs):
            s,l,n=futs[f]
            try:
                gs=f.result(); print(f"  {n} ({l}): {len(gs)} games in next {DAYS_AHEAD} days")
                for g in gs: g["league_name"]=n
                all_games.extend(gs)
            except Exception as e: print(f"  Fetch fail {n}: {e}")
    seen=set(); uniq=[]
    for g in all_games:
        k=(clean(g["home"]), clean(g["away"]), g["date"], g.get("time",""))
        if k not in seen: seen.add(k); uniq.append(g)
    print(f"TOTAL UNIQUE GAMES NEXT {DAYS_AHEAD} DAYS: {len(uniq)}")
    return uniq
def run_picker():
    now=lagos_now(); print("="*60); print(f"V13.4 STRICT - Lagos now: {now.strftime('%Y-%m-%d %H:%M')} - 30 days, 2 REAL games or SKIP"); print("="*60); load_cache()
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
    tickets={"football_book_now": f_now_ticket, "football_book_now_total": f_now_total, "football_weekend": f_weekend_ticket, "football_weekend_total": f_weekend_total, "basketball_book_now": b_now_ticket, "basketball_book_now_total": b_now_total, "basketball_weekend": b_weekend_ticket, "basketball_weekend_total": b_weekend_total, "generated_at_lagos": now.isoformat()}
    with open("tickets.json","w",encoding="utf-8") as f: json.dump(tickets,f,indent=2,ensure_ascii=False)
    print("\n"+"="*60)
    print(f"FOOTBALL BOOK NOW STRICT: {len(f_now_ticket)} games | TOTAL ~{f_now_total} | Pool {len(f_now_cands)}")
    if f_now_total < TARGET_TOTAL_ODD: print(f"  -> STRICT: BOOK NOW football cannot reach 8000 today with strict picks. Do NOT force it. Wait for WEEKEND.")
    for i,g in enumerate(f_now_ticket,1): print(f"{i}. [{g.get('league_name')} {g['date']} {g.get('time','')} Lagos - BOOK NOW] {g['home']} vs {g['away']} - {g['market']} @ {g['est_odd']} | {g['reason']}")
    print(f"\nFOOTBALL WEEKEND STRICT: {len(f_weekend_ticket)} games | TOTAL ~{f_weekend_total} | Pool {len(f_weekend_cands)}")
    for i,g in enumerate(f_weekend_ticket,1): print(f"{i}. [{g.get('league_name')} {g['date']} {g.get('time','')} Lagos - WAIT] {g['home']} vs {g['away']} - {g['market']} @ {g['est_odd']} | {g['reason']}")
    print(f"\nBASKETBALL BOOK NOW STRICT: {len(b_now_ticket)} games | TOTAL ~{b_now_total} | Pool {len(b_now_cands)}")
    for i,g in enumerate(b_now_ticket,1): print(f"{i}. [{g.get('league_name')} {g['date']} {g.get('time','')} Lagos - BOOK NOW] {g['home']} vs {g['away']} - {g['market']} @ {g['est_odd']} | {g['reason']}")
    print(f"\nBASKETBALL WEEKEND STRICT: {len(b_weekend_ticket)} games | TOTAL ~{b_weekend_total} | Pool {len(b_weekend_cands)}")
    for i,g in enumerate(b_weekend_ticket,1): print(f"{i}. [{g.get('league_name')} {g['date']} {g.get('time','')} Lagos - WAIT] {g['home']} vs {g['away']} - {g['market']} @ {g['est_odd']} | {g['reason']}")
    print(f"\nSKIPS (STRICT - this is good): {FAIL['skip']}")
    print("STRICT RULE: Every pick above has 2 REAL games in last 30 days + passed strict gap. No weak fills.")

def auto_book():
    from playwright.sync_api import sync_playwright
    try:
        with open("tickets.json", encoding="utf-8") as f: tickets=json.load(f)
    except: print("No tickets.json - run --pick first"); return
    print(f"\nAUTO BOOK V13.4 STRICT - Only BOOK NOW")
    with sync_playwright() as p:
        browser=p.chromium.launch_persistent_context(user_data_dir="./sporty_profile", headless=False, args=["--start-maximized"])
        page=browser.pages[0] if browser.pages else browser.new_page(); page.goto(SPORTYBET_NG)
        input(">>> LOG IN. Press ENTER once...")
        for ticket_name in ["football_book_now","basketball_book_now"]:
            games=tickets.get(ticket_name,[]); print(f"\n=== {ticket_name} - {len(games)} games ==="); added=0
            for idx,g in enumerate(games,1):
                try:
                    page.goto(f"https://www.sportybet.com/ng/search?query={g['home']}", timeout=20000); page.wait_for_timeout(2200)
                    clicked=False; btns=page.query_selector_all("button, div[class*='odd']")
                    for b in btns:
                        try:
                            txt=b.inner_text().strip(); want=g["market"]; want_short="1" if want.startswith("1 -") else "2" if want.startswith("2 -") else want
                            if txt==want_short or txt.startswith(want_short+" "): b.click(); print(f"[{idx}] ADDED {g['date']} {g.get('time','')} {g['home']} vs {g['away']} - {g['market']}"); added+=1; clicked=True; break
                        except: continue
                    if not clicked: print(f"[{idx}] NOT FOUND: {g['home']} vs {g['away']} - {g['market']}")
                    page.wait_for_timeout(700)
                except Exception as e: print(f"[{idx}] ERROR {e}")
            print(f"{ticket_name}: Added {added}/{len(games)}")
            if DRY_RUN:
                try: page.evaluate("() => { const b=[...document.querySelectorAll('button')].find(x=>x.innerText.includes('Clear')); if(b) b.click(); }")
                except: pass
            else: input(">>> Press ENTER after you placed this ticket...")
        print("DONE"); input("Press ENTER to close..."); browser.close()

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "--pick"
    if mode=="--book-auto": auto_book()
    else: run_picker()
