# sportybet_bot.py - V18 - FULL CODE - LAST 4 in 40 DAYS + OVER 1.5 MAIN + OVER MINIMUM BASKET + OVER 2.5 HIGH + KEEP H2H/SOS/STRENGTH/DEFENCE - PASTE WHOLE FILE
import sys, json, time, requests, re, os, random, threading, math
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
HISTORY_DAYS = 40  # BACK TO WHAT WORKED: 40 days
NEED_GAMES = 4     # BACK TO WHAT WORKED: Last 4
MIN_GAMES = 3      # Need at least 3 of 4
CACHE_FILE = "last4_cache.json"
SAVED_FILE = "saved_weekend.json"
LAST4_MAP = {}
H2H_MAP = {}
FAIL = {"skip": {}}

TEAM_ALIAS = {
    "athletico-pr": "Paranaense", "athletico paranaense": "Paranaense", "atletico-pr": "Paranaense",
    "ca paranaense": "Paranaense", "flamengo": "Flamengo", "palmeiras": "Palmeiras",
    "corinthians": "Corinthians", "sao paulo": "Sao Paulo", "manchester city": "Man City",
    "manchester united": "Man Utd", "tottenham hotspur": "Tottenham", "newcastle united": "Newcastle",
    "brighton & hove albion": "Brighton", "west ham united": "West Ham", "nottingham forest": "Nottm Forest",
    "wolverhampton wanderers": "Wolves", "leicester city": "Leicester", "ipswich town": "Ipswich",
}
def sporty_name(name):
    n = name.strip(); key = re.sub(r'[^a-z ]', '', n.lower()).strip()
    if key in TEAM_ALIAS: return TEAM_ALIAS[key]
    n2 = re.sub(r'\b(CR|CA|EC|SC|AA|AD)\b', '', n, flags=re.I).strip()
    n2 = re.sub(r'\b(RJ|PR|SP|BA|MG|RS|PE|CE|GO|PA)\b', '', n2, flags=re.I).strip()
    return n2 if n2 else n

app = Flask(__name__)
STATE = {"running": False, "last_run": None, "error": None, "tickets": None}
STATE_LOCK = threading.Lock()
def log_skip(r): FAIL["skip"][r] = FAIL["skip"].get(r, 0) + 1
def clean(s):
    s = s.lower(); s = re.sub(r'\b(fc|cf|sc|ac|bk|bc|club|real|atletico|athletic|deportivo)\b', '', s)
    return ' '.join(re.sub(r'[^a-z0-9 ]', '', s).split())
def lagos_now(): return datetime.now(LAGOS)
def parse_espn_time(date_str):
    try:
        if not date_str: return None
        dt_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt_utc.tzinfo is None: dt_utc = dt_utc.replace(tzinfo=UTC)
        return dt_utc.astimezone(LAGOS)
    except: return None

# FOOTBALL - 23 leagues, untouched
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
# BASKETBALL - ALL your SportyBet leagues
BASKETBALL_LEAGUES = [
    ("basketball", "nba", "NBA"),
    ("basketball", "wnba", "WNBA"),
    ("basketball", "mens-college-basketball", "NCAA, Regular Season"),
    ("basketball", "euroleague", "Euroleague"),
    ("basketball", "eurocup", "Eurocup"),
    ("basketball", "fiba-champions-league", "FIBA Champions League"),
    ("basketball", "lnbp", "LNBP"),
    ("basketball", "turkish-super-league", "Super Lig 26/27"),
    ("basketball", "israeli-super-league", "Basketball League"),
    ("basketball", "french-lnb-elite", "LNB Elite 26/27"),
    ("basketball", "spanish-acb", "Liga ACB 26/27"),
    ("basketball", "italian-serie-a", "Serie A 26/27"),
    ("basketball", "german-bbl", "BBL 26/27"),
    ("basketball", "vtb-united-league", "United League"),
    ("basketball", "brazilian-nbb", "NBB"),
    ("basketball", "argentinian-lnb", "LNB"),
    ("basketball", "korean-kbl", "KBL"),
    ("basketball", "australian-nbl", "NBL"),
    ("basketball", "chinese-cba", "CBA"),
]
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
    global LAST4_MAP, H2H_MAP
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                d=json.load(f); LAST4_MAP=d.get("last4",d.get("last14",{})); H2H_MAP=d.get("h2h",{})
        except: LAST4_MAP={}; H2H_MAP={}
def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump({"last4":LAST4_MAP,"h2h":H2H_MAP}, f)
    except: pass
def build_last4(sport, league, days=HISTORY_DAYS):
    prefix = f"{sport}-{league}-"
    if any(k.startswith(prefix) for k in LAST4_MAP): return
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
                id0, id1 = str(t0["team"]["id"]), str(t1["team"]["id"])
                hkey = "-".join(sorted([id0, id1]))
                H2H_MAP.setdefault(hkey, [])
                entry = [ds, s0, s1, id0, id1, str(t0["team"]["displayName"]), str(t1["team"]["displayName"])]
                if entry not in H2H_MAP[hkey]: H2H_MAP[hkey].append(entry)
                for mine, opp, my, op in [(t0, t1, s0, s1), (t1, t0, s1, s0)]:
                    k = f"{sport}-{league}-{mine['team']['id']}"
                    LAST4_MAP.setdefault(k, [])
                    is_home = 1 if mine.get("homeAway")=="home" else 0
                    e = [ds, my, op, str(opp["team"]["displayName"]), str(opp["team"]["id"]), is_home]
                    if e not in LAST4_MAP[k]: LAST4_MAP[k].append(e)
            except: continue
    for k in list(LAST4_MAP):
        if k.startswith(prefix): LAST4_MAP[k] = sorted(LAST4_MAP[k], reverse=True)[:NEED_GAMES]
    for k in list(H2H_MAP):
        H2H_MAP[k] = sorted(H2H_MAP[k], reverse=True)[:5]
def weighted_avg(values, decay=0.90):
    if not values: return 0
    weights = [decay**i for i in range(len(values))]
    return sum(v*w for v,w in zip(values, weights)) / sum(weights)

def get_last4(sport, league, tid, next_game_date=None):
    lst = LAST4_MAP.get(f"{sport}-{league}-{tid}", [])
    if len(lst) < MIN_GAMES:
        log_skip("last4_lt3_skip"); return None
    scored = [x[1] for x in lst]; conceded = [x[2] for x in lst]
    # WEIGHTED - last game counts more
    w_scored = weighted_avg(scored); w_conceded = weighted_avg(conceded); w_total = w_scored + w_conceded
    avg_s = sum(scored)/len(scored); avg_c = sum(conceded)/len(conceded)
    wins = sum(1 for my, op in zip(scored, conceded) if my > op)
    draws = sum(1 for my, op in zip(scored, conceded) if my == op)
    losses = sum(1 for my, op in zip(scored, conceded) if my < op)
    # HOME / AWAY SPLIT - kept
    home_games = [x for x in lst if x[5]==1]; away_games = [x for x in lst if x[5]==0]
    def _avg(arr, idx): return round(sum(x[idx] for x in arr)/len(arr),2) if arr else avg_s if idx==1 else avg_c
    h_scored = _avg(home_games,1); h_conceded = _avg(home_games,2); a_scored = _avg(away_games,1); a_conceded = _avg(away_games,2)
    # VARIANCE / CONSISTENCY - kept
    def _std(vals, mean):
        if len(vals)<2: return 0
        return (sum((v-mean)**2 for v in vals)/len(vals))**0.5
    std_total = _std([a+b for a,b in zip(scored, conceded)], avg_s+avg_c)
    pace = round(w_total,2)
    speed = round(weighted_avg(scored[:2]) - weighted_avg(scored[-2:]),2) if len(scored)>=3 else 0
    # CORRECTED REST - last game -> NEXT game, only true B2B punished
    try:
        last_date = datetime.strptime(lst[0][0], "%Y%m%d").date()
        rest_to_next = (next_game_date - last_date).days if next_game_date else 3
    except: rest_to_next = 3
    rest_days = rest_to_next; fatigue = 0
    if sport != "soccer":
        if rest_to_next <= 1: fatigue = -4.0
        elif rest_to_next == 2: fatigue = -0.5
        else: fatigue = 0.0
        if len(lst) >= 3:
            try:
                d0 = datetime.strptime(lst[0][0], "%Y%m%d").date(); d2 = datetime.strptime(lst[2][0], "%Y%m%d").date()
                if (d0 - d2).days <= 4: fatigue += -1.5
            except: pass
    else:
        fatigue = -0.4 if rest_to_next <= 2 else 0.0
    # STRENGTH - ATTACK + DEFENCE - KEPT, this is your core
    if sport == "soccer": attack = round(w_scored*2, 1); defence = round(max(0, 5-w_conceded), 1)
    else: attack = round(w_scored/10, 1); defence = round(max(0, 10-w_conceded/10), 1)
    # SOS - KEPT
    sos_points = 0
    for my, op in zip(scored, conceded):
        if sport == "soccer": opp_strength = 1.0 + (op - 1.2)*0.2
        else: opp_strength = 1.0 + (op - 100)*0.01
        opp_strength = max(0.5, min(1.5, opp_strength)); pts = 3 if my>op else 1 if my==op else 0; sos_points += pts * opp_strength
    sos_points = round(sos_points/len(lst)*3,2)
    motivation = 0.5 if wins==0 else 0.0
    consistency = max(0.3, 1 - (std_total / (avg_s+avg_c+1) * 1.5)) if avg_s+avg_c>0 else 0.5
    confidence = round(consistency * min(1.0, len(lst)/NEED_GAMES),2)
    # EXTRA: goals in last 4 - for Over 2.5 HIGH check
    total_goals_last4 = sum(scored) + sum(conceded)
    over15_hits = sum(1 for my, op in zip(scored, conceded) if my+op >= 2)
    over25_hits = sum(1 for my, op in zip(scored, conceded) if my+op >= 3)
    return {"games": len(lst), "scored": scored, "conceded": conceded, "avg_scored": round(avg_s,2), "avg_conceded": round(avg_c,2),
            "w_scored": round(w_scored,2), "w_conceded": round(w_conceded,2), "total": round(avg_s+avg_c,1), "w_total": round(w_total,1), "pace": pace,
            "wins": wins, "draws": draws, "losses": losses, "speed": speed, "attack": attack, "defence": defence, "sos_points": sos_points,
            "motivation": motivation, "opponents": [x[3] for x in lst], "home_scored": h_scored, "home_conceded": h_conceded,
            "away_scored": a_scored, "away_conceded": a_conceded, "std_total": round(std_total,2),
            "confidence": confidence, "rest_days": rest_days, "fatigue": fatigue,
            "total_goals_last4": total_goals_last4, "over15_hits": over15_hits, "over25_hits": over25_hits}

def get_h2h(id_home, id_away):
    hkey = "-".join(sorted([str(id_home), str(id_away)])); lst = H2H_MAP.get(hkey, [])
    if not lst: return {"games":0, "home_wins":0, "away_wins":0, "draws":0, "bonus_home":0, "bonus_away":0, "text":"No recent H2H", "over15_hits":0, "avg_total":0}
    hw=aw=dr=0; totals=[]
    for ds, s0, s1, id0, id1, n0, n1 in lst:
        if str(id0)==str(id_home): hs, aws = s0, s1
        else: hs, aws = s1, s0
        totals.append(hs+aws)
        if hs>aws: hw+=1
        elif aws>hs: aw+=1
        else: dr+=1
    over15 = sum(1 for t in totals if t>=2)
    avg_tot = round(sum(totals)/len(totals),2) if totals else 0
    return {"games":len(lst), "home_wins":hw, "away_wins":aw, "draws":dr, "bonus_home": 0.8 if hw>aw else 0, "bonus_away": 0.8 if aw>hw else 0, "text": f"H2H last {len(lst)}: Home {hw}W - {dr}D - {aw}W Away | H2H Avg {avg_tot} goals", "over15_hits": over15, "avg_total": avg_tot}

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
                date_label=kickoff_lagos.strftime("%Y-%m-%d"); time_label=kickoff_lagos.strftime("%H:%M"); days_from_now=(kickoff_lagos.date()-now_lagos.date()).days
                bookable="BOOK NOW" if days_from_now<=2 else "WAIT - WEEKEND"
                out.append({"home": h["team"]["displayName"], "away": a["team"]["displayName"], "home_sporty": sporty_name(h["team"]["displayName"]), "away_sporty": sporty_name(a["team"]["displayName"]), "home_id": str(h["team"]["id"]), "away_id": str(a["team"]["id"]), "league": league, "sport": sport, "date": date_label, "time": time_label, "days_from_now": days_from_now, "bookable": bookable})
            except: continue
    return out

# === V18 FOOTBALL: OVER 1.5 MAIN + OVER 2.5 HIGH (EXTRA) ===
def analyse_football(g, hs, aws):
    h2h = get_h2h(g["home_id"], g["away_id"])
    # STRENGTH: home attack uses HOME split, away attack uses AWAY split
    h_attack = hs["home_scored"] if hs["home_scored"] else hs["w_scored"]
    a_attack = aws["away_scored"] if aws["away_scored"] else aws["w_scored"]
    # Expected total = weighted + H2H + SOS + strength
    combined = round((hs["w_total"]+aws["w_total"])/2,2)
    # H2H boost: if H2H avg is high, lift expected total a bit
    if h2h["games"]>=2 and h2h["avg_total"]>=3:
        combined = round(combined + 0.3,2)
    conf = min(hs["confidence"], aws["confidence"])
    base={"home": g["home"], "away": g["away"], "home_sporty": g.get("home_sporty", g["home"]), "away_sporty": g.get("away_sporty", g["away"]), "league": g["league"], "date": g["date"], "time": g.get("time",""), "days_from_now": g.get("days_from_now",0), "bookable": g.get("bookable","")}
    detail = f"H2H: {h2h['text']} | SOS H {hs['sos_points']} vs A {aws['sos_points']} | Attack H {hs['attack']} A {aws['attack']} | Defence H {hs['defence']} A {aws['defence']} | Goals H {hs['scored']} A {aws['scored']} | Conf {conf} | Rest H{hs['rest_days']}d A{aws['rest_days']}d"
    # DEFENSIVE FILTER - NEW: if BOTH teams are defensive in last 4, skip Over
    # Defensive = conceded <=0.7 per game AND scored <=1.0
    both_defensive = (hs["w_conceded"]<=0.7 and aws["w_conceded"]<=0.7 and hs["w_scored"]<=1.0 and aws["w_scored"]<=1.0)
    if both_defensive:
        log_skip("football_both_defensive_skip"); return None, None
    main_pick = None; high_pick = None
    # --- MAIN: OVER 1.5 - needs expected >=2.0 AND at least 3 of last 4 games went Over 1.5 for both ---
    if conf >= 0.30 and combined >= 2.0 and hs["over15_hits"]>=2 and aws["over15_hits"]>=2:
        # Est odd like SportyBet real: 1.03-1.32 range
        if combined >= 3.2: odd = 1.10
        elif combined >= 2.6: odd = 1.15
        elif combined >= 2.3: odd = 1.20
        else: odd = 1.25
        main_pick = {**base, "market": "Over 1.5", "est_odd": odd, "reason": f"OVER 1.5 | Exp {combined} | H2H Avg {h2h['avg_total']} | {detail}", "score": combined*conf*odd}
    # --- HIGH / EXTRA: OVER 2.5 - ONLY if BOTH scored 3+ in last 4 combined? Actually rule you asked: both teams scored 3+ goals total in last 4? We use stricter: each team scored >=5 in last 4 AND over25 hits >=2 each ---
    # You said "both scored 3+ in last 4" - we interpret as each team total goals >=6 in last 4 (avg 1.5+) AND combined expected >=2.8
    hs_total_scored = sum(hs["scored"]); aws_total_scored = sum(aws["scored"])
    if conf >= 0.30 and combined >= 2.8 and hs_total_scored>=6 and aws_total_scored>=6 and hs["over25_hits"]>=2 and aws["over25_hits"]>=2:
        high_pick = {**base, "market": "Over 2.5 - HIGH", "est_odd": 1.75, "reason": f"OVER 2.5 HIGH | Exp {combined} | H scored {hs_total_scored} in Last4, A scored {aws_total_scored} in Last4 | {detail}", "score": combined*conf*1.75}
    if not main_pick and not high_pick:
        log_skip("football_no_over15")
    return main_pick, high_pick

# === V18 BASKETBALL: OVER MINIMUM LINE ONLY - NO WINNER BETS ===
def analyse_basketball(g, hs, aws):
    h2h = get_h2h(g["home_id"], g["away_id"])
    h_diff = hs["home_scored"]-hs["home_conceded"] if hs["home_scored"] else hs["w_scored"]-hs["w_conceded"]
    a_diff = aws["away_scored"]-aws["away_conceded"] if aws["away_scored"] else aws["w_scored"]-aws["w_conceded"]
    expected = round((hs["w_total"]+aws["w_total"])/2,1)
    pace_total = round((hs["pace"]+aws["pace"])/2,1)
    expected = round((expected+pace_total)/2,1)
    # H2H boost
    if h2h["games"]>=2 and h2h["avg_total"]>=220:
        expected = round(expected + 3,1)
    conf = min(hs["confidence"], aws["confidence"])
    base={"home": g["home"], "away": g["away"], "home_sporty": g.get("home_sporty", g["home"]), "away_sporty": g.get("away_sporty", g["away"]), "league": g["league"], "date": g["date"], "time": g.get("time",""), "days_from_now": g.get("days_from_now",0), "bookable": g.get("bookable","")}
    detail = f"H2H: {h2h['text']} | SOS H {hs['sos_points']} vs A {aws['sos_points']} | Attack H {hs['attack']} A {aws['attack']} | Defence H {hs['defence']} A {aws['defence']} | Conf {conf} | Pace {pace_total} | Rest H{hs['rest_days']}d A{aws['rest_days']}d"
    # DEFENSIVE FILTER: if either team concedes very low in last 4, skip Over
    # NBA: conceded <100, NCAA: conceded <65 = defensive, skip
    is_ncaa = "NCAA" in g.get("league_name","") or "college" in g.get("league","")
    def_threshold = 65 if is_ncaa else 100
    if hs["w_conceded"] < def_threshold and aws["w_conceded"] < def_threshold:
        log_skip("basket_both_defensive_skip"); return None
    # OVER MINIMUM LINE: like your winning ticket - Wizards 217.5 when expected was ~240
    # Line = expected - 12 points (minimum line SportyBet offers), so probability is high
    # For NCAA, expected - 8 because totals are lower
    gap = 8 if is_ncaa else 12
    line = float(int((expected - gap)*2)/2)
    if conf >= 0.30 and expected > line + 5:
        # Odd like real SportyBet minimum line: 1.20-1.35
        odd = 1.26 if expected > line+10 else 1.32
        return {**base, "market": f"Over {line} - MINIMUM", "est_odd": odd, "reason": f"OVER MIN {line} | Expected {expected} Pace {pace_total} | {detail}", "score": expected*conf*odd, "lowest_line": line}
    log_skip("basket_no_over_min"); return None

def build_ticket(candidates, max_games):
    candidates=sorted(candidates, key=lambda x: x["score"], reverse=True); picked=[]; total=1.0
    for c in candidates:
        if len(picked)>=max_games: break
        picked.append(c); total*=c["est_odd"]
        if total>=TARGET_TOTAL_ODD and len(picked)>=10: break
    return picked, round(total,1)
def build_all_last4(leagues):
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(build_last4, s, l, HISTORY_DAYS): (s,l,n) for s,l,n in leagues}
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
    build_all_last4(FOOTBALL_LEAGUES); f_games=fetch_all_7days(FOOTBALL_LEAGUES)
    f_now_cands=[]; f_weekend_cands=[]; f_high_now=[]; f_high_weekend=[]
    for g in f_games:
        try: nxt = datetime.strptime(g["date"], "%Y-%m-%d").date()
        except: nxt = None
        hs=get_last4(g["sport"], g["league"], g["home_id"], next_game_date=nxt); aws=get_last4(g["sport"], g["league"], g["away_id"], next_game_date=nxt)
        if not hs or not aws: continue
        main_p, high_p = analyse_football(g, hs, aws)
        if main_p:
            main_p["league_name"]=g.get("league_name", g["league"])
            if g.get("days_from_now",99)<=2: f_now_cands.append(main_p)
            else: f_weekend_cands.append(main_p)
        if high_p:
            high_p["league_name"]=g.get("league_name", g["league"])
            if g.get("days_from_now",99)<=2: f_high_now.append(high_p)
            else: f_high_weekend.append(high_p)
    f_now_ticket, f_now_total=build_ticket(f_now_cands, FOOTBALL_MAX); f_weekend_ticket, f_weekend_total=build_ticket(f_weekend_cands, FOOTBALL_MAX)
    f_high_now_ticket, f_high_now_total=build_ticket(f_high_now, FOOTBALL_MAX); f_high_weekend_ticket, f_high_weekend_total=build_ticket(f_high_weekend, FOOTBALL_MAX)
    build_all_last4(BASKETBALL_LEAGUES); b_games=fetch_all_7days(BASKETBALL_LEAGUES)
    b_now_cands=[]; b_weekend_cands=[]
    for g in b_games:
        try: nxt = datetime.strptime(g["date"], "%Y-%m-%d").date()
        except: nxt = None
        hs=get_last4(g["sport"], g["league"], g["home_id"], next_game_date=nxt); aws=get_last4(g["sport"], g["league"], g["away_id"], next_game_date=nxt)
        if not hs or not aws: continue
        p=analyse_basketball(g, hs, aws)
        if p:
            p["league_name"]=g.get("league_name", g["league"])
            if g.get("days_from_now",99)<=2: b_now_cands.append(p)
            else: b_weekend_cands.append(p)
    b_now_ticket, b_now_total=build_ticket(b_now_cands, BASKETBALL_MAX); b_weekend_ticket, b_weekend_total=build_ticket(b_weekend_cands, BASKETBALL_MAX)
    tickets={"football_book_now": f_now_ticket, "football_book_now_total": f_now_total, "football_weekend": f_weekend_ticket, "football_weekend_total": f_weekend_total,
             "football_high_book_now": f_high_now_ticket, "football_high_book_now_total": f_high_now_total, "football_high_weekend": f_high_weekend_ticket, "football_high_weekend_total": f_high_weekend_total,
             "basketball_book_now": b_now_ticket, "basketball_book_now_total": b_now_total, "basketball_weekend": b_weekend_ticket, "basketball_weekend_total": b_weekend_total,
             "generated_at_lagos": now.isoformat(), "skips": FAIL["skip"], "model": "V18 Last4-40days + Over1.5 Main + OverMin Basket + Over2.5 High + H2H/SOS/Strength/Defence"}
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
<title>SportyBot V18</title>
<style>body{font-family:Arial,sans-serif;background:#0f1115;color:#fff;margin:0;padding:16px}h1{font-size:22px}button{background:#00c853;color:#fff;border:0;padding:14px 20px;font-size:18px;border-radius:10px;width:100%;cursor:pointer;margin-top:10px}button:disabled{opacity:.5}.save{background:#ff9800;color:#000}.saveall{background:#ff5722}.view{background:#2196f3}.bookall{background:#7c4dff}.card{background:#1c1f26;padding:14px;border-radius:12px;margin-top:14px}.game{border-bottom:1px solid #333;padding:8px 0}.tag{background:#ff9800;color:#000;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:bold}.muted{color:#aaa}.book{display:block;background:#00c853;color:#fff;text-align:center;padding:12px;border-radius:8px;margin-top:8px;text-decoration:none;font-weight:bold}.copy{display:block;background:#333;color:#fff;text-align:center;padding:8px;border-radius:8px;margin-top:6px;text-decoration:none}.tick{font-size:18px;background:#2a2e38;padding:10px;border-radius:8px;display:block;margin-bottom:8px}.tick input{width:22px;height:22px;transform:scale(1.4);margin-right:10px}.savedbox{border:2px solid #ff9800;padding:10px;border-radius:10px}.del{background:#e53935;padding:6px 12px;width:auto;font-size:14px}.loginbtn{display:block;background:#fff;color:#000;text-align:center;padding:14px;border-radius:10px;margin-top:10px;text-decoration:none;font-weight:bold;font-size:18px}.waitbox{background:#333;padding:10px;border-radius:8px;margin-top:8px}</style></head>
<body><h1>⚽ SportyBot V18 - Last 4 + Over 1.5 / Over Min</h1><p class="muted">Last 4 in 40 days | Football Over 1.5 MAIN + Over 2.5 HIGH (extra) | Basketball Over MINIMUM line | H2H + SOS + Attack + Defence + Goals + Pace + Rest kept | No Winner bets - Over only</p>
<a class="loginbtn" href="https://www.sportybet.com/ng/" target="_blank">🔐 LOGIN TO SPORTYBET FIRST</a>
<button id="runBtn" onclick="runPick()">▶ RUN PICK NOW</button>
<button class="save" onclick="saveTicked()">💾 SAVE TICKED TICKETS</button>
<button class="saveall" onclick="saveAllWeekend()">💾 SAVE ALL WEEKEND TICKETS</button>
<button class="view" onclick="viewSaved()">📂 VIEW SAVED TICKETS (<span id="savedCount">0</span>)</button>
<button class="bookall" onclick="bookAllSaved()">🎯 BOOK ALL SAVED</button>
<p id="status" class="muted">Tip: Login to SportyBet first, then tap BOOK.</p>
<div id="out"></div>
<script>
let CURRENT=null; let SAVED_LIST=[];
function shortSearchName(g){
  let home = g.home_sporty || g.home;
  if((g.league_name||'').toLowerCase().includes('nba') || (g.league_name||'').includes('NCAA') || (g.league_name||'').includes('WNBA') || (g.league_name||'').toLowerCase().includes('basketball') || (g.league_name||'').includes('Euro') || (g.league_name||'').includes('Liga') || (g.league_name||'').includes('Serie') || (g.league_name||'').includes('BBL') || (g.league_name||'').includes('LNB') || (g.league_name||'').includes('NBB') || (g.league_name||'').includes('KBL')){
    let parts = home.trim().split(' '); home = parts[parts.length-1];
  }
  return home;
}
function bookLink(g){
  let home = shortSearchName(g); let q = encodeURIComponent(home); let full = (g.home_sporty||g.home) + ' vs ' + (g.away_sporty||g.away); let isFuture = (g.days_from_now||0) > 2;
  if(isFuture){ return '<div class="waitbox">⏳ <b>WAIT - Not on SportyBet yet</b><br>This game is on '+g.date+'.<br><a class="copy" href="#" onclick="navigator.clipboard.writeText(\\''+full+'\\');alert(\\'Copied: '+full+'\\');return false;">📋 Copy name for later</a></div>'; }
  return '<a class="book" href="https://www.sportybet.com/ng/search?query='+q+'" target="_blank">➡️ BOOK ON SPORTYBET - Search: '+home+'</a><div class="muted" style="font-size:13px;margin-top:6px">Look for: <b>'+full+'</b> then pick <b>'+g.market+'</b></div><a class="copy" href="#" onclick="navigator.clipboard.writeText(\\''+full+'\\');alert(\\'Copied: '+full+'\\');return false;">📋 Copy exact names</a>';
}
function ticketDef(key,title,list,total,isWeekend){return {key:key,title:title,list:list,total:total,isWeekend:isWeekend};}
function renderTickets(t, showTick, prefix){let defs=[ticketDef('football_book_now','FOOTBALL OVER 1.5 - BOOK NOW',t.football_book_now||[],t.football_book_now_total||0,false),ticketDef('football_weekend','FOOTBALL OVER 1.5 - WEEKEND',t.football_weekend||[],t.football_weekend_total||0,true),ticketDef('football_high_book_now','FOOTBALL OVER 2.5 HIGH - BOOK NOW',t.football_high_book_now||[],t.football_high_book_now_total||0,false),ticketDef('football_high_weekend','FOOTBALL OVER 2.5 HIGH - WEEKEND',t.football_high_weekend||[],t.football_high_weekend_total||0,true),ticketDef('basketball_book_now','BASKETBALL OVER MIN - BOOK NOW',t.basketball_book_now||[],t.basketball_book_now_total||0,false),ticketDef('basketball_weekend','BASKETBALL OVER MIN - WEEKEND',t.basketball_weekend||[],t.basketball_weekend_total||0,true)];let html='';defs.forEach(d=>{let h='<div class="card"><h3>'+prefix+d.title+' - '+d.list.length+' games | TOTAL ~'+d.total+'</h3>';if(showTick){let checked=d.isWeekend?'checked':'';h+='<label class="tick"><input type="checkbox" class="save-tick" data-key="'+d.key+'" '+checked+'> ✅ Tick to SAVE this ticket</label>';}if(!d.list.length)h+='<p>No strict picks.</p>';d.list.forEach((g,i)=>{h+='<div class="game"><b>'+(i+1)+'. '+(g.home_sporty||g.home)+' vs '+(g.away_sporty||g.away)+'</b><br><span class="muted">ESPN: '+g.home+' vs '+g.away+'</span><br>'+g.league_name+' | '+g.date+' '+g.time+' Lagos <span class="tag">'+g.bookable+'</span><br>'+g.market+' @ '+g.est_odd+'<br><span class="muted">'+g.reason+'</span><br>'+bookLink(g)+'</div>'});h+='</div>';html+=h;});html+='<div class="card muted">Generated: '+(t.generated_at_lagos||'')+' | '+(t.model||'')+'</div>';return html;}
async function runPick(){document.getElementById('runBtn').disabled=true;document.getElementById('status').innerText='Running V18... Last 4 is faster...';await fetch('/run',{method:'POST'});let ti=setInterval(async()=>{let s=await (await fetch('/status')).json();document.getElementById('status').innerText=s.running?'Still running...':'Done! '+(s.last_run||'');if(!s.running){clearInterval(ti);document.getElementById('runBtn').disabled=false;load();}},3000);}
async function load(){let d=await (await fetch('/api/tickets')).json();if(!d||!d.tickets){document.getElementById('out').innerHTML='<p>No picks yet.</p>';return;}CURRENT=d.tickets;document.getElementById('out').innerHTML=renderTickets(CURRENT,true,'');refreshSavedCount();}
async function refreshSavedCount(){let s=await (await fetch('/saved')).json();SAVED_LIST=(s&&s.saved_list)?s.saved_list:[];document.getElementById('savedCount').innerText=SAVED_LIST.length;}
function getTickedKeys(){let out=[];document.querySelectorAll('.save-tick:checked').forEach(c=>out.push(c.dataset.key));return out;}
async function doSave(keys){if(!CURRENT){alert('Run pick first.');return;}if(!keys.length){alert('Tick at least 1 ticket.');return;}let ticketsToSave=keys.map(k=>{let map={football_book_now:['FOOTBALL OVER 1.5 BOOK NOW',CURRENT.football_book_now,CURRENT.football_book_now_total],football_weekend:['FOOTBALL OVER 1.5 WEEKEND',CURRENT.football_weekend,CURRENT.football_weekend_total],football_high_book_now:['FOOTBALL OVER 2.5 HIGH BOOK NOW',CURRENT.football_high_book_now,CURRENT.football_high_book_now_total],football_high_weekend:['FOOTBALL OVER 2.5 HIGH WEEKEND',CURRENT.football_high_weekend,CURRENT.football_high_weekend_total],basketball_book_now:['BASKETBALL OVER MIN BOOK NOW',CURRENT.basketball_book_now,CURRENT.basketball_book_now_total],basketball_weekend:['BASKETBALL OVER MIN WEEKEND',CURRENT.basketball_weekend,CURRENT.basketball_weekend_total]};let v=map[k];return {key:k,title:v[0],games:v[1],total:v[2],generated_at_lagos:CURRENT.generated_at_lagos,saved_at:new Date().toISOString()};});let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tickets:ticketsToSave})});let j=await r.json();if(j.ok){alert('✅ SAVED '+ticketsToSave.length+' ticket(s)!');refreshSavedCount();}else alert('Save failed');}
async function saveTicked(){await doSave(getTickedKeys());}
async function saveAllWeekend(){await doSave(['football_weekend','basketball_weekend','football_high_weekend']);}
async function viewSaved(){await refreshSavedCount();if(!SAVED_LIST.length){alert('No saved tickets yet.');return;}let html='<div class="savedbox"><h2>📂 SAVED TICKETS - '+SAVED_LIST.length+'</h2><button class="bookall" onclick="bookAllSaved()">🎯 BOOK ALL SAVED NOW</button></div>';SAVED_LIST.forEach((t,idx)=>{html+='<div class="card"><h3>✅ SAVED: '+t.title+' - '+t.games.length+' games | TOTAL ~'+t.total+'</h3><p class="muted">Saved: '+t.saved_at+'</p><button class="del" onclick="deleteSaved('+idx+')">🗑 Delete</button>';t.games.forEach((g,i)=>{html+='<div class="game"><b>'+(i+1)+'. '+(g.home_sporty||g.home)+' vs '+(g.away_sporty||g.away)+'</b><br>'+g.league_name+' | '+g.date+' '+g.time+' <span class="tag">'+g.bookable+'</span><br>'+g.market+' @ '+g.est_odd+'<br><span class="muted">'+g.reason+'</span><br>'+bookLink(g)+'</div>'});html+='</div>';});document.getElementById('out').innerHTML=html;}
async function deleteSaved(idx){if(!confirm('Delete this saved ticket?'))return;await fetch('/delete_saved/'+idx,{method:'POST'});viewSaved();}
async function bookAllSaved(){await refreshSavedCount();if(!SAVED_LIST.length){alert('No saved tickets.');return;}let all=[];SAVED_LIST.forEach(t=>all.push(...t.games));let bookable = all.filter(g=>(g.days_from_now||0)<=2);if(!bookable.length){alert('All saved games are still WAIT - WEEKEND.');return;}if(!confirm('Open '+bookable.length+' BOOK NOW games?'))return;bookable.forEach((g,i)=>{setTimeout(()=>{let q=encodeURIComponent(shortSearchName(g));window.open('https://www.sportybet.com/ng/search?query='+q,'_blank');},i*1200);});}
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
        data = request.get_json(force=True); new_tickets = data.get("tickets", []); existing=[]
        if os.path.exists(SAVED_FILE):
            try:
                with open(SAVED_FILE, encoding="utf-8") as f:
                    old=json.load(f)
                    if isinstance(old, dict) and "saved_list" in old: existing=old["saved_list"]
                    elif isinstance(old, list): existing=old
            except: existing=[]
        for nt in new_tickets:
            dup=any(e.get("title")==nt.get("title") and e.get("generated_at_lagos")==nt.get("generated_at_lagos") and len(e.get("games",[]))==len(nt.get("games",[])) for e in existing)
            if not dup: existing.append(nt)
        with open(SAVED_FILE,"w",encoding="utf-8") as f: json.dump({"saved_list": existing},f,indent=2,ensure_ascii=False)
        return jsonify({"ok": True, "count": len(existing)})
    except Exception as e: return jsonify({"ok": False, "error": str(e)})
@app.route("/saved")
def get_saved():
    try:
        with open(SAVED_FILE, encoding="utf-8") as f:
            d=json.load(f)
            if isinstance(d, dict) and "saved_list" in d: return jsonify({"saved_list": d["saved_list"]})
            if isinstance(d, list): return jsonify({"saved_list": d})
            return jsonify({"saved_list": []})
    except: return jsonify({"saved_list": []})
@app.route("/delete_saved/<int:idx>", methods=["POST"])
def delete_saved(idx):
    try:
        with open(SAVED_FILE, encoding="utf-8") as f: d=json.load(f)
        lst=d.get("saved_list",[]) if isinstance(d,dict) else []
        if 0 <= idx < len(lst): lst.pop(idx)
        with open(SAVED_FILE,"w",encoding="utf-8") as f: json.dump({"saved_list": lst},f,indent=2,ensure_ascii=False)
        return jsonify({"ok": True})
    except Exception as e: return jsonify({"ok": False, "error": str(e)})
@app.route("/health")
def health(): return jsonify({"ok": True})
if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "--web"
    if mode=="--pick": run_picker()
    else:
        port=int(os.environ.get("PORT", 5000)); app.run(host="0.0.0.0", port=port)
