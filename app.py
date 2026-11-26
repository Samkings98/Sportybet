# job_finder.py - Job Finder for Samson Agbi - FULL FILE V2
# Email now includes: Apply Link + Tailored Cover Letter + Tailored CV for each job
import json, os, threading, re, requests, time, smtplib
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, render_template_string, request
from email.mime.text import MIMEText

LAGOS = ZoneInfo("Africa/Lagos")
app = Flask(__name__)

# ===== YOUR PROFILE - Samson Agbi =====
PROFILE = {
    "name": "Samson Agbi",
    "email": "samkinsonlog@gmail.com",
    "location": "Nigeria / Africa/Lagos",
    "timezone": "Africa/Lagos (WAT, GMT+1) - Flexible for US / UK shifts",
    "title": "Remote Customer Chat Support | Data Entry | Virtual Assistant | AI Trainer",
    "summary": "Reliable remote support professional from Nigeria with strong written English, fast typing, and high accuracy. Experienced in live chat support, data entry, virtual assistance, and AI training tasks. Available for flexible shifts including US/UK time zones, with stable internet and quiet work setup.",
    "skills": [
        "Customer Chat Support - Live chat, email support, Zendesk / Intercom / Freshdesk",
        "Data Entry & Accuracy - 60+ WPM typing, Google Sheets / Excel, data cleaning, CRM updating",
        "Virtual Assistant - Calendar, email management, scheduling, research, admin tasks",
        "AI Training / Data Labelling - Prompt testing, response rating, data annotation, content review, QA",
        "Communication - Clear written English, professional chat etiquette, de-escalation, fast response",
        "Tools - Google Workspace, Microsoft Office, Slack, Discord, WhatsApp Business, Notion, Trello",
    ],
    "strengths": [
        "99%+ accuracy on data tasks",
        "Fast learner, follows SOPs exactly",
        "Available for US / UK time zones, night / weekend shifts",
        "Stable internet + laptop, quiet work setup",
        "Professional, patient, and reliable under pressure",
    ],
    "experience": [
        "Remote Support & Admin Assistant (Freelance / Remote) - Handled live chat, email support, data entry, scheduling and research for online clients. Maintained high accuracy and fast response times.",
        "Data Entry & AI Training Tasks (Remote) - Completed data cleaning, labelling, prompt rating and QA tasks for AI / online platforms. Delivered on time with attention to detail.",
        "Online Customer Support (Remote) - Resolved customer questions via chat/email, escalated issues correctly, kept tickets updated in CRM.",
    ]
}

STATE = {"running": False, "last_run": None, "error": None, "jobs": None}
STATE_LOCK = threading.Lock()
SAVED_FILE = "saved_jobs.json"

# ===== CURATED LEGIT EASY-ENTRY JOBS =====
# Legit jobs NEVER ask you to pay to join. If a site asks for upfront fee, leave it.
CURATED = [
    {"title": "Customer Support Agent - Chat", "company": "SupportNinja", "location": "Remote - Worldwide", "type": "Chat Support", "salary": "$800 - $1500 / month", "url": "https://www.supportninja.com/careers", "tags": ["chat", "support"], "description": "Chat + email support. Training provided. No phone, just typing."},
    {"title": "Customer Support Specialist", "company": "PartnerHero", "location": "Remote - Worldwide", "type": "Chat Support", "salary": "Competitive", "url": "https://www.partnerhero.com/careers", "tags": ["chat", "support"], "description": "Remote support for international brands. Flexible shifts."},
    {"title": "Live Chat Agent - No Phone", "company": "The Chat Shop", "location": "Remote - Worldwide", "type": "Chat Support", "salary": "$10 - $14 / hour", "url": "https://www.thechatshop.com/careers", "tags": ["chat", "support"], "description": "Pure live chat job. No phone calls. Good English + typing needed."},
    {"title": "Online Chat Moderator", "company": "ModSquad", "location": "Remote - Worldwide", "type": "Chat / Moderation", "salary": "Hourly - Flexible", "url": "https://modsquad.com/careers/", "tags": ["chat", "moderator"], "description": "Moderate chats, forums, communities. Flexible hours, pick your shifts."},
    {"title": "AI Trainer / AI Rater", "company": "DataAnnotation", "location": "Remote - Worldwide", "type": "AI Training", "salary": "$20+ / hour (project based)", "url": "https://www.dataannotation.tech/", "tags": ["ai", "training"], "description": "Read AI answers, rate them, correct them. No coding needed."},
    {"title": "AI Trainer - Outlier", "company": "Outlier AI", "location": "Remote - Worldwide", "type": "AI Training", "salary": "Hourly - Flexible", "url": "https://outlier.ai/", "tags": ["ai", "training"], "description": "AI rater - read, rate, improve AI responses. Flexible, work anytime."},
    {"title": "AI Data Annotator", "company": "Remotasks", "location": "Remote - Worldwide", "type": "AI Training / Data Entry", "salary": "Per task - PayPal", "url": "https://www.remotasks.com/", "tags": ["ai", "data entry"], "description": "Label data, check images/text for AI. Pays per task to PayPal."},
    {"title": "Content Moderator / Rater", "company": "TELUS Digital", "location": "Remote - Worldwide", "type": "AI / Moderation", "salary": "Per task", "url": "https://www.telusdigital.com/careers", "tags": ["ai", "moderator"], "description": "Rate search results, moderate content, data tasks. No face needed."},
    {"title": "Data Entry / AI Tasks", "company": "Appen", "location": "Remote - Worldwide", "type": "Data Entry / AI", "salary": "Per task", "url": "https://appen.com/jobs/", "tags": ["data entry", "ai"], "description": "Micro tasks, data labelling, search rating. Pays to PayPal / Payoneer."},
    {"title": "Micro Tasks - Data Entry", "company": "Clickworker", "location": "Remote - Worldwide", "type": "Data Entry", "salary": "Per task - PayPal", "url": "https://www.clickworker.com/", "tags": ["data entry"], "description": "Small tasks: data entry, surveys, text checks. Start with phone/laptop."},
    {"title": "Virtual Assistant", "company": "Belay / Time Etc", "location": "Remote - Worldwide", "type": "Virtual Assistant", "salary": "$15 - $25 / hour", "url": "https://belaysolutions.com/careers/", "tags": ["virtual assistant"], "description": "Email, calendar, admin, research for clients. No face."},
    {"title": "Customer Support - Chat", "company": "LiveChat", "location": "Remote", "type": "Chat Support", "salary": "Competitive", "url": "https://www.livechat.com/careers/", "tags": ["chat", "support"], "description": "Chat support roles for SaaS companies."},
]

def lagos_now():
    return datetime.now(LAGOS)

def clean_text(s):
    if not s: return ""
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:600]

def fetch_remoteok():
    jobs = []
    try:
        r = requests.get("https://remoteok.com/api", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            for j in data[1:80]:
                title = (j.get("position") or "").lower()
                if any(k in title for k in ["support", "chat", "customer", "data", "virtual", "assistant", "moderator", "annotator", "ai", "admin", "help"]):
                    jobs.append({
                        "title": j.get("position", "Remote Role"),
                        "company": j.get("company", "RemoteOK Company"),
                        "location": "Remote - " + (j.get("location") or "Worldwide"),
                        "type": "Remote",
                        "salary": (str(j.get("salary_min") or "") + " - " + str(j.get("salary_max") or "")) if j.get("salary_min") else "See listing",
                        "url": j.get("url") or j.get("apply_url") or "https://remoteok.com",
                        "tags": j.get("tags", [])[:5] if isinstance(j.get("tags"), list) else [],
                        "description": clean_text(j.get("description", "")),
                        "source": "RemoteOK"
                    })
    except Exception as e:
        print("RemoteOK fail:", e)
    return jobs

def fetch_arbeitnow():
    jobs = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=20)
        if r.status_code == 200:
            data = r.json().get("data", [])
            for j in data[:80]:
                title = (j.get("title") or "").lower()
                if any(k in title for k in ["support", "chat", "customer", "data", "virtual", "assistant", "moderator", "ai", "admin"]):
                    jobs.append({
                        "title": j.get("title"),
                        "company": j.get("company_name", "Company"),
                        "location": "Remote - " + (j.get("location") or "Worldwide"),
                        "type": "Remote",
                        "salary": "See listing",
                        "url": j.get("url", "https://www.arbeitnow.com"),
                        "tags": j.get("tags", [])[:5] if isinstance(j.get("tags"), list) else [],
                        "description": clean_text(j.get("description", "")),
                        "source": "Arbeitnow"
                    })
    except Exception as e:
        print("Arbeitnow fail:", e)
    return jobs

def score_job(job):
    t = (job.get("title","") + " " + job.get("company","")).lower()
    score = 0
    for kw in ["chat support", "customer support", "data entry", "virtual assistant", "ai trainer", "ai rater"]:
        if kw in t: score += 10
    if "remote" in (job.get("location","").lower()): score += 5
    return score

def make_cv_text(job):
    lines = []
    lines.append(f"{PROFILE['name']}")
    lines.append(f"{PROFILE['title']}")
    lines.append(f"Email: {PROFILE['email']} | Location: {PROFILE['location']} | {PROFILE['timezone']}")
    lines.append("")
    lines.append("SUMMARY:")
    lines.append(PROFILE['summary'])
    lines.append("")
    lines.append(f"WHY FIT FOR {job.get('title','')} at {job.get('company','')}:")
    lines.append(f"Strong match for {job.get('title','')} - experienced in chat support, data accuracy, and remote admin work. Fast, reliable, and ready to start.")
    lines.append("")
    lines.append("SKILLS:")
    for s in PROFILE['skills']: lines.append("- " + s)
    lines.append("")
    lines.append("RELIABILITY:")
    for s in PROFILE['strengths']: lines.append("- " + s)
    lines.append("")
    lines.append("EXPERIENCE:")
    for e in PROFILE['experience']: lines.append("- " + e)
    return "\n".join(lines)

def make_cover_text(job):
    return f"""Dear {job.get('company','Hiring Team')} Hiring Team,

I am Samson Agbi from Nigeria, applying for {job.get('title','')} at {job.get('company','')}.

I am a reliable remote worker with strong written English, 60+ WPM typing, and 99%+ accuracy. I have experience in customer chat support, data entry, virtual assistance, and AI training tasks - handling live chat, tickets, data cleaning, scheduling, and QA with fast response times.

I work well on US/UK shifts, follow SOPs exactly, and keep communication clear and professional. I have stable internet, a laptop, and a quiet setup, and I am ready to start immediately.

I would love to help your team deliver fast, friendly, and accurate support.

Thank you for considering me.

Best regards,
Samson Agbi
samkinsonlog@gmail.com
Nigeria / Africa/Lagos
"""

def fetch_all_jobs():
    all_jobs = []
    all_jobs += CURATED
    all_jobs += fetch_remoteok()
    all_jobs += fetch_arbeitnow()
    seen = set(); uniq = []
    for j in all_jobs:
        k = (j.get("title","").lower(), j.get("company","").lower())
        if k not in seen:
            seen.add(k); j["score"] = score_job(j); uniq.append(j)
    uniq = sorted(uniq, key=lambda x: x.get("score",0), reverse=True)
    for j in uniq:
        j["cv_text"] = make_cv_text(j)
        j["cover_text"] = make_cover_text(j)
    return uniq

def run_finder():
    jobs = fetch_all_jobs()
    out = {"generated_at_lagos": lagos_now().isoformat(), "total": len(jobs), "jobs": jobs, "profile": PROFILE}
    with open("jobs.json", "w", encoding="utf-8") as f: json.dump(out, f, indent=2, ensure_ascii=False)
    with STATE_LOCK: STATE["jobs"] = out
    return out

def _run_bg():
    with STATE_LOCK: STATE["running"] = True; STATE["error"] = None
    try:
        run_finder()
        with STATE_LOCK: STATE["last_run"] = lagos_now().isoformat()
    except Exception as e:
        with STATE_LOCK: STATE["error"] = str(e)
    finally:
        with STATE_LOCK: STATE["running"] = False

# ===== DAILY EMAIL DIGEST - V2 - Includes Apply Link + Cover Letter + CV per job =====
# In Render -> Environment, add:
# EMAIL_USER = samkinsonlog@gmail.com
# EMAIL_PASS = your Gmail App Password (16 letters, NOT normal password)
# EMAIL_TO = samkinsonlog@gmail.com
# SITE_URL = https://your-render-link.onrender.com  (optional, for link back to site)
def send_daily_email():
    jobs_data = run_finder()
    # Send top 10 only - so email is not too long, and Gmail does not block it
    jobs = jobs_data.get("jobs", [])[:10]
    if not jobs:
        return "No jobs found"

    site_url = os.environ.get("SITE_URL", "Open your Render link")
    body = f"Hi Samson,\n\n"
    body += f"You have {len(jobs)} new remote jobs today - {lagos_now().strftime('%Y-%m-%d')} Lagos time.\n"
    body += "All are legit, no-face, easy-entry. Do NOT pay any site to join.\n"
    body += "HOW TO APPLY: 1) Copy the Cover Letter below 2) Click the Apply link 3) Paste Cover Letter + CV\n"
    body += f"Your site for all jobs + CVs: {site_url}\n"
    body += "\n========================================\n"

    for idx, j in enumerate(jobs, 1):
        body += f"\nJOB {idx}: {j['title']} at {j['company']}\n"
        body += f"Location: {j['location']} | Salary: {j['salary']}\n"
        body += f"APPLY LINK - CLICK HERE: {j['url']}\n"
        body += f"\n--- TAILORED COVER LETTER - COPY THIS ---\n"
        body += j.get("cover_text", "") + "\n"
        body += f"\n--- TAILORED CV - COPY THIS ---\n"
        body += j.get("cv_text", "") + "\n"
        body += "\n----------------------------------------\n"

    body += "\nTip: Apply to 10 per day. Start with the Chat Support + AI Trainer ones first - they hire fastest.\n"
    body += "Good luck today Samson!\n"

    user = os.environ.get("EMAIL_USER")
    pw = os.environ.get("EMAIL_PASS")
    to = os.environ.get("EMAIL_TO", "samkinsonlog@gmail.com")
    if not user or not pw:
        return "EMAIL_USER / EMAIL_PASS not set in Render - skipping email. Set them in Render Environment."

    msg = MIMEText(body)
    msg["Subject"] = f"💼 {len(jobs)} New Remote Jobs For You - With Cover Letters + CVs - {lagos_now().strftime('%Y-%m-%d')}"
    msg["From"] = user
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, pw)
        server.sendmail(user, [to], msg.as_string())
    return f"Sent {len(jobs)} jobs with Cover Letters + CVs to {to}"

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Samson Job Finder - Remote Jobs</title>
<style>body{font-family:Arial,sans-serif;background:#0f1115;color:#fff;margin:0;padding:16px}h1{font-size:22px}button{background:#00c853;color:#fff;border:0;padding:14px 20px;font-size:18px;border-radius:10px;width:100%;cursor:pointer;margin-top:10px}.cv{background:#673ab7}.save{background:#ff9800;color:#000}.email{background:#2196f3}.card{background:#1c1f26;padding:14px;border-radius:12px;margin-top:14px}.tag{background:#ff9800;color:#000;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:bold}.muted{color:#aaa}.book{display:block;background:#00c853;color:#fff;text-align:center;padding:12px;border-radius:8px;margin-top:8px;text-decoration:none;font-weight:bold}.tabbar{display:flex;gap:8px;margin-top:12px}.tabbar button{padding:10px;font-size:15px}.tabbar button.active{background:#fff;color:#000}textarea{width:100%;height:180px;background:#111;color:#fff;border:1px solid #333;border-radius:8px;padding:10px}.warn{background:#3a2a00;border:2px solid #ff9800;padding:12px;border-radius:10px;margin-top:12px}</style></head>
<body><h1>💼 Samson Job Finder - Remote Jobs</h1><p class="muted">Samson Agbi | samkinsonlog@gmail.com | Nigeria / Africa/Lagos | Chat Support • Data Entry • VA • AI Training</p>
<div class="warn">⚠️ <b>Legit rule:</b> Never pay to join a job. Legit jobs pay YOU. If a site asks for upfront fee, leave it. No face needed for these jobs.<br>📧 Daily email now includes Apply Link + Cover Letter + CV for each job.</div>
<div class="tabbar"><button id="tabHome" class="active" onclick="showTab('home')">🏠 JOBS</button><button id="tabCV" onclick="showTab('cv')">📄 MY CV</button><button id="tabSaved" onclick="showTab('saved')">📂 SAVED (<span id="savedCount">0</span>)</button></div>
<div id="view-home">
<button id="runBtn" onclick="runFind()">▶ FIND REMOTE JOBS NOW</button>
<button class="email" onclick="sendDigest()">📧 SEND ME TODAY'S JOBS BY EMAIL (With Cover Letters + CVs)</button>
<p id="status" class="muted">Loading...</p>
<label>Filter: <select id="filter" onchange="renderFilter()"><option value="all">All Jobs</option><option value="Chat Support">Chat Support</option><option value="Data Entry">Data Entry</option><option value="AI Training">AI Training</option><option value="Virtual Assistant">Virtual Assistant</option></select></label>
<div id="out"></div>
</div>
<div id="view-cv" style="display:none"><h2>📄 Your CV - Samson Agbi</h2><p class="muted">Copy this, paste into Word / Google Docs, or use per-job version below.</p><textarea id="cvBox"></textarea><button onclick="copyCV()">📋 Copy CV</button><button class="cv" onclick="downloadCV()">⬇ Download CV .txt</button></div>
<div id="view-saved" style="display:none"><button onclick="showTab('home')">⬅ BACK</button><div id="savedOut"></div></div>
<script>
let CURRENT=null; let SAVED=[];
function showTab(n){document.getElementById('view-home').style.display=n==='home'?'block':'none';document.getElementById('view-cv').style.display=n==='cv'?'block':'none';document.getElementById('view-saved').style.display=n==='saved'?'block':'none';document.getElementById('tabHome').classList.toggle('active',n==='home');document.getElementById('tabCV').classList.toggle('active',n==='cv');document.getElementById('tabSaved').classList.toggle('active',n==='saved');if(n==='saved')viewSaved();if(n==='cv')loadCV();}
function renderFilter(){if(!CURRENT)return;renderJobs(CURRENT);}
function renderJobs(d){let f=document.getElementById('filter').value;let jobs=d.jobs.filter(j=>f==='all'||(j.title+j.type+j.tags.join(' ')).toLowerCase().includes(f.toLowerCase())||(f==='AI Training'&&j.title.toLowerCase().includes('ai')));let h='';jobs.forEach((j,i)=>{h+='<div class="card"><b>'+(i+1)+'. '+j.title+'</b><br>'+j.company+' | '+j.location+' | <span class="tag">'+j.type+'</span> | '+j.salary+'<br><span class="muted">'+(j.description||'Easy-entry remote role - click Apply to see full details.')+'</span><br><a class="book" href="'+j.url+'" target="_blank">➡️ APPLY NOW - '+j.company+'</a><button onclick="toggleCover('+i+')">✉️ Show Tailored Cover Letter</button><button class="cv" onclick="toggleCV('+i+')">📄 Show Tailored CV</button><button class="save" onclick="saveOne('+i+')">💾 Save Job</button><div id="cover-'+i+'" style="display:none"><textarea>'+j.cover_text+'</textarea><button onclick="copyText(\\'cover-'+i+'\\')">📋 Copy Cover Letter</button></div><div id="cv-'+i+'" style="display:none"><textarea>'+j.cv_text+'</textarea><button onclick="copyText(\\'cv-'+i+'\\')">📋 Copy CV</button></div></div>';});document.getElementById('out').innerHTML=h||'<p>No jobs for this filter.</p>';}
function toggleCover(i){let e=document.getElementById('cover-'+i);e.style.display=e.style.display==='none'?'block':'none';}
function toggleCV(i){let e=document.getElementById('cv-'+i);e.style.display=e.style.display==='none'?'block':'none';}
function copyText(id){let ta=document.querySelector('#'+id+' textarea');ta.select();document.execCommand('copy');alert('Copied! Paste into application.');}
async function runFind(){document.getElementById('runBtn').disabled=true;document.getElementById('status').innerText='Searching...';await fetch('/run',{method:'POST'});let ti=setInterval(async()=>{let s=await (await fetch('/status')).json();if(!s.running){clearInterval(ti);document.getElementById('runBtn').disabled=false;load();}},3000);}
async function sendDigest(){document.getElementById('status').innerText='Sending email...';let r=await (await fetch('/send-digest')).json();alert(r.result||'Sent! Check email');document.getElementById('status').innerText=r.result||'Sent';}
async function load(){let d=await (await fetch('/api/jobs')).json();if(d&&d.jobs){CURRENT=d.jobs;renderJobs(CURRENT);document.getElementById('status').innerText='Found '+CURRENT.total+' jobs - Generated: '+CURRENT.generated_at_lagos;}else{document.getElementById('status').innerText='No jobs yet. Click FIND.';}refreshSaved();}
async function loadCV(){let d=await (await fetch('/api/profile')).json();if(d&&d.profile){let p=d.profile;let cv=p.name+'\\n'+p.title+'\\nEmail: '+p.email+' | '+p.location+'\\n\\nSUMMARY:\\n'+p.summary+'\\n\\nSKILLS:\\n- '+p.skills.join('\\n- ')+'\\n\\nRELIABILITY:\\n- '+p.strengths.join('\\n- ')+'\\n\\nEXPERIENCE:\\n- '+p.experience.join('\\n- ');document.getElementById('cvBox').value=cv;}}
function copyCV(){let t=document.getElementById('cvBox');t.select();document.execCommand('copy');alert('CV copied!');}
function downloadCV(){let blob=new Blob([document.getElementById('cvBox').value],{type:'text/plain'});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='Samson-Agbi-CV.txt';a.click();}
async function saveOne(i){let job=CURRENT.jobs[i];await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobs:[job]})});alert('Saved: '+job.title);refreshSaved();}
async function refreshSaved(){let s=await (await fetch('/saved')).json();SAVED=s.saved_list||[];document.getElementById('savedCount').innerText=SAVED.length;}
async function viewSaved(){await refreshSaved();if(!SAVED.length){document.getElementById('savedOut').innerHTML='<p>No saved jobs yet.</p>';return;}let h='';SAVED.forEach((j,i)=>{h+='<div class="card"><b>'+j.title+'</b><br>'+j.company+' | '+j.location+'<br><a class="book" href="'+j.url+'" target="_blank">➡️ APPLY</a></div>';});document.getElementById('savedOut').innerHTML=h;}
load();
</script></body></html>
"""

@app.route("/")
def home(): return render_template_string(HTML)
@app.route("/status")
def status():
    with STATE_LOCK: return jsonify({"running": STATE["running"], "last_run": STATE["last_run"], "error": STATE["error"]})
@app.route("/api/jobs")
def api_jobs():
    with STATE_LOCK:
        if STATE["jobs"]: return jsonify({"jobs": STATE["jobs"]})
    try:
        with open("jobs.json", encoding="utf-8") as f: return jsonify({"jobs": json.load(f)})
    except: return jsonify({"jobs": None})
@app.route("/api/profile")
def api_profile(): return jsonify({"profile": PROFILE})
@app.route("/run", methods=["POST"])
def run():
    with STATE_LOCK:
        if STATE["running"]: return jsonify({"ok": False})
    th = threading.Thread(target=_run_bg, daemon=True); th.start()
    return jsonify({"ok": True})
@app.route("/send-digest")
def send_digest_route():
    try:
        result = send_daily_email()
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "result": str(e)})
@app.route("/save", methods=["POST"])
def save():
    try:
        data = request.get_json(force=True); new_jobs = data.get("jobs", []); existing=[]
        if os.path.exists(SAVED_FILE):
            try:
                with open(SAVED_FILE, encoding="utf-8") as f: existing=json.load(f).get("saved_list",[])
            except: existing=[]
        for nj in new_jobs:
            dup = any(e.get("title")==nj.get("title") and e.get("company")==nj.get("company") for e in existing)
            if not dup: existing.append(nj)
        with open(SAVED_FILE,"w",encoding="utf-8") as f: json.dump({"saved_list": existing}, f, indent=2, ensure_ascii=False)
        return jsonify({"ok": True, "count": len(existing)})
    except Exception as e: return jsonify({"ok": False, "error": str(e)})
@app.route("/saved")
def get_saved():
    try:
        with open(SAVED_FILE, encoding="utf-8") as f: return jsonify({"saved_list": json.load(f).get("saved_list",[])})
    except: return jsonify({"saved_list": []})
@app.route("/health")
def health(): return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
