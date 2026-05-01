import json
import os
import time
import secrets
import string
import hashlib
import requests
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, send_from_directory
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import mimetypes

### --- CONFIGURATION ---
USER_HOME = "jacobjones"
BASE = f"/home/{USER_HOME}" if os.path.exists(f"/home/{USER_HOME}") else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data.json")

SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "CHANGE_ME_TO_A_RANDOM_STRING")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

DEFAULT_GAME_THUMB = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSyKJiMb4HJ1m8GAEBmKQ4TsJOjge7aAWOHzw&s"
DEFAULT_PROFILE_PIC = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRbuAuWYEv06bkCkP_1OsDlGBA6nCtw3ANZ1Q&s"

# --- Helper Functions ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_random_password(length=8):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_roblox_avatar_url(username):
    """Get the current Roblox avatar URL without saving it"""
    if not username:
        return DEFAULT_PROFILE_PIC
    try:
        u_res = requests.post("https://users.roblox.com/v1/usernames/users",
                              json={"usernames": [username], "excludeBannedUsers": True}, timeout=5)
        if u_res.status_code != 200:
            return DEFAULT_PROFILE_PIC
        user_data = u_res.json()
        if 'data' not in user_data or len(user_data['data']) == 0:
            return DEFAULT_PROFILE_PIC
            
        uid = user_data['data'][0]['id']
        t_res = requests.get(f"https://thumbnails.roblox.com/v1/users/avatar?userIds={uid}&size=720x720&format=Png&isCircular=false", timeout=5)
        if t_res.status_code != 200:
            return DEFAULT_PROFILE_PIC
        thumb_data = t_res.json()
        if 'data' not in thumb_data or len(thumb_data['data']) == 0:
            return DEFAULT_PROFILE_PIC
        return thumb_data['data'][0]['imageUrl']
    except:
        return DEFAULT_PROFILE_PIC

def is_admin(username):
    db = load_db()
    return username in db.get('admins', [])

def get_display_name(username):
    db = load_db()
    return db['users'].get(username, {}).get('display_name', username)

def get_pfp(username):
    db = load_db()
    rbx = db['users'].get(username, {}).get('rbx')
    return get_roblox_avatar_url(rbx) if rbx else DEFAULT_PROFILE_PIC

def load_db():
    if not os.path.exists(DB_PATH):
        init = {
            "users": {
                "Mega": {
                    "p": hash_password("defaultpass"),
                    "rbx": "Megamonster8312",
                    "must_reset_password": True,
                    "display_name": "Mega",
                    "avatar_file": None
                }
            },
            "games": [],
            "ann": "Welcome to the site!",
            "bans": {},
            "admins": ["Mega"],
            "messages": []
        }
        with open(DB_PATH, 'w') as f: json.dump(init, f, indent=4)
        return init
    with open(DB_PATH, 'r') as f:
        try: return json.load(f)
        except: return {
            "users": {
                "Mega": {
                    "p": hash_password("defaultpass"),
                    "rbx": "Megamonster8312",
                    "must_reset_password": True,
                    "display_name": "Mega",
                    "avatar_file": None
                }
            },
            "games": [],
            "ann": "Welcome to the site!",
            "bans": {},
            "admins": ["Mega"],
            "messages": []
        }

def save_db(data):
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=4)
        os.fsync(f.fileno())

def is_banned(username):
    db = load_db()
    bans = db.get('bans', {})
    if username not in bans:
        return False, None
    ban_info = bans[username]
    if ban_info.get('permanent', False):
        return True, ban_info
    expiry = ban_info.get('expires', 0)
    if expiry > 0 and time.time() > expiry:
        del bans[username]
        save_db(db)
        return False, None
    return True, ban_info

### --- CSS (Emerald UI) ---
CSS = """
:root {
    --bg-primary: #0c0f15;
    --bg-secondary: #151a23;
    --bg-card: rgba(21, 26, 35, 0.7);
    --border-light: rgba(255, 255, 255, 0.06);
    --border-accent: rgba(45, 212, 191, 0.25);
    --accent-primary: #2dd4bf;
    --accent-secondary: #14b8a6;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --danger: #f87171;
    --success: #4ade80;
    --warning: #fbbf24;
    --sidebar-width: 280px;
    --header-height: 70px;
    --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    font-size: 16px;
}

body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: radial-gradient(circle at 20% 30%, rgba(45, 212, 191, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 80% 70%, rgba(20, 184, 166, 0.06) 0%, transparent 40%);
    pointer-events: none;
    z-index: 0;
    animation: bgPulse 15s ease infinite alternate;
}

@keyframes bgPulse { 0% { opacity: 0.5; } 100% { opacity: 1; } }

.header {
    background: rgba(12, 15, 21, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border-light);
    padding: 0 32px;
    height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    animation: slideDown 0.4s ease;
}

@keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.logo {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.5px;
    background: linear-gradient(135deg, #fff, var(--accent-primary));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    position: relative;
}

.logo::after {
    content: '';
    position: absolute;
    bottom: -4px;
    left: 0;
    width: 100%;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent-primary), transparent);
    transform: scaleX(0);
    transition: transform 0.3s ease;
    transform-origin: left;
}

.logo:hover::after { transform: scaleX(1); }

.user-info {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    padding: 6px 16px 6px 12px;
    border-radius: 40px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-light);
    transition: var(--transition);
}

.user-info:hover {
    background: rgba(45, 212, 191, 0.1);
    border-color: var(--border-accent);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.user-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid var(--border-light);
    transition: var(--transition);
}

.user-info:hover .user-avatar { border-color: var(--accent-primary); transform: scale(1.05); }

.username { font-size: 14px; font-weight: 500; color: var(--text-primary); }

.announcement {
    background: linear-gradient(135deg, #0f2a2b, #0a1e1f);
    color: var(--accent-primary);
    text-align: center;
    padding: 10px;
    font-size: 13px;
    font-weight: 500;
    border-bottom: 1px solid rgba(45, 212, 191, 0.15);
    animation: slideDown 0.4s ease 0.05s both;
    position: relative;
    overflow: hidden;
}

.announcement::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 200%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(45, 212, 191, 0.05), transparent);
    animation: shimmer 4s infinite;
}

@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }

.layout { display: flex; flex: 1; overflow: hidden; position: relative; z-index: 1; }

.sidebar {
    width: var(--sidebar-width);
    background: rgba(12, 15, 21, 0.9);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-right: 1px solid var(--border-light);
    padding: 24px 12px;
    overflow-y: auto;
    height: calc(100vh - var(--header-height));
    position: sticky;
    top: var(--header-height);
    animation: slideRight 0.4s ease;
}

@keyframes slideRight { from { transform: translateX(-20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

.nav-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 16px;
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 15px;
    font-weight: 500;
    border-radius: 12px;
    margin-bottom: 4px;
    transition: var(--transition);
    position: relative;
}

.nav-item i { width: 22px; font-size: 1.2rem; transition: var(--transition); }

.nav-item:hover {
    background: rgba(45, 212, 191, 0.08);
    color: var(--text-primary);
    transform: translateX(4px);
}

.nav-item:hover i { color: var(--accent-primary); }

.nav-item.active {
    background: rgba(45, 212, 191, 0.12);
    color: var(--accent-primary);
    border-left: 3px solid var(--accent-primary);
}

.nav-item.active i { color: var(--accent-primary); }

.divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-light), transparent);
    margin: 20px 12px;
}

.logout-item { color: var(--danger); }
.logout-item:hover { background: rgba(248, 113, 113, 0.1); color: var(--danger); }
.logout-item:hover i { color: var(--danger); }

.main-content {
    flex: 1;
    overflow-y: auto;
    padding: 32px 40px;
    background: transparent;
    animation: fadeIn 0.5s ease;
    margin-left: 0;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.card {
    background: var(--bg-card);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid var(--border-light);
    border-radius: 24px;
    padding: 28px;
    margin-bottom: 24px;
    transition: var(--transition);
    animation: cardAppear 0.4s ease both;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

@keyframes cardAppear { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }

.card:hover {
    border-color: var(--border-accent);
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    transform: translateY(-2px);
}

.welcome-card {
    text-align: center;
    max-width: 600px;
    margin: 0 auto;
    background: linear-gradient(135deg, rgba(21, 26, 35, 0.9), rgba(12, 15, 21, 0.95));
    border: 1px solid rgba(45, 212, 191, 0.15);
}

.welcome-icon { font-size: 64px; margin-bottom: 24px; color: var(--accent-primary); display: inline-block; animation: float 4s ease-in-out infinite; }

@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }

.welcome-title {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #fff, var(--accent-primary));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.welcome-text { color: var(--text-secondary); line-height: 1.6; font-size: 15px; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 24px; margin-top: 20px; }

.game-card { cursor: pointer; overflow: hidden; padding: 0; background: var(--bg-card); }

.media-preview {
    width: 100%;
    height: 160px;
    object-fit: cover;
    background: linear-gradient(135deg, #1e293b, #0f172a);
    transition: var(--transition);
}

.game-card:hover .media-preview { transform: scale(1.03); }

.media-title { font-size: 16px; font-weight: 600; margin: 16px 0 8px 0; padding: 0 16px; color: var(--text-primary); }

.media-creator { font-size: 13px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; padding: 0 16px 16px 16px; }

.manage-link { display: inline-block; margin: 8px 16px 16px 16px; font-size: 13px; color: var(--accent-primary); text-decoration: none; font-weight: 500; transition: var(--transition); }
.manage-link:hover { text-decoration: underline; opacity: 0.9; }

.form-group { margin-bottom: 20px; animation: slideUp 0.3s ease both; }

@keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

label { display: block; margin-bottom: 6px; font-size: 14px; font-weight: 500; color: var(--text-secondary); }

input, textarea, select {
    width: 100%;
    padding: 12px 16px;
    background: rgba(15, 23, 31, 0.8);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    font-size: 14px;
    color: var(--text-primary);
    transition: var(--transition);
    font-family: inherit;
}

input:focus, textarea:focus, select:focus {
    outline: none;
    border-color: var(--accent-primary);
    background: rgba(21, 26, 35, 0.9);
    box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.1);
}

textarea { resize: vertical; min-height: 100px; }

.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 40px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: var(--transition);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    text-decoration: none;
    border: 1px solid transparent;
}

.btn-primary { background: var(--accent-primary); color: #0c0f15; font-weight: 600; }
.btn-primary:hover { background: var(--accent-secondary); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(45, 212, 191, 0.25); }
.btn-danger { background: var(--danger); color: white; }
.btn-danger:hover { background: #ef4444; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(248, 113, 113, 0.25); }
.btn-secondary { background: rgba(255, 255, 255, 0.05); color: var(--text-primary); border: 1px solid var(--border-light); }
.btn-secondary:hover { background: rgba(255, 255, 255, 0.1); transform: translateY(-2px); }
.btn-success { background: var(--success); color: #0c0f15; font-weight: 600; }
.btn-success:hover { background: #22c55e; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(74, 222, 128, 0.25); }

.modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.95); backdrop-filter: blur(16px); cursor: pointer; animation: fadeIn 0.3s ease; }
.modal-content { margin: auto; display: block; max-width: 90%; max-height: 90%; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }
.modal-content img { width: auto; height: auto; max-width: 100%; max-height: 90vh; border-radius: 20px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }
.close-modal { position: absolute; top: 20px; right: 35px; color: #fff; font-size: 40px; font-weight: bold; transition: var(--transition); cursor: pointer; z-index: 1001; }
.close-modal:hover { color: var(--accent-primary); transform: rotate(90deg); }

.profile-container { display: flex; gap: 40px; align-items: center; flex-wrap: wrap; }
.profile-avatar { width: 140px; height: 140px; border-radius: 50%; object-fit: cover; border: 3px solid var(--border-light); transition: var(--transition); }
.profile-avatar:hover { border-color: var(--accent-primary); transform: scale(1.02); }
.profile-name { font-size: 32px; font-weight: 700; margin-bottom: 8px; background: linear-gradient(135deg, #fff, var(--accent-primary)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.profile-display-name { font-size: 18px; color: var(--accent-primary); margin-bottom: 8px; }
.profile-roblox { color: var(--text-secondary); margin-bottom: 16px; font-size: 15px; }
.admin-badge { display: inline-block; background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)); color: #0c0f15; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-left: 12px; }

.table-container { overflow-x: auto; margin-top: 16px; border-radius: 16px; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 14px; border-bottom: 2px solid var(--border-light); font-weight: 600; color: var(--text-secondary); font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }
td { padding: 14px; border-bottom: 1px solid var(--border-light); color: var(--text-primary); transition: background 0.2s; }
tr:hover td { background: rgba(255, 255, 255, 0.02); }

.status-banned { color: var(--danger); font-weight: 500; }
.status-active { color: var(--success); font-weight: 500; }
.status-admin { color: var(--accent-primary); font-weight: 500; }

.ban-notice { max-width: 500px; margin: 80px auto; padding: 40px; background: var(--bg-card); backdrop-filter: blur(12px); border: 1px solid var(--border-light); border-radius: 32px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2); }
.ban-notice i { font-size: 56px; margin-bottom: 20px; color: var(--danger); }
.ban-notice h1 { font-size: 28px; margin-bottom: 20px; color: var(--danger); }
.ban-notice p { color: var(--text-secondary); line-height: 1.6; margin-bottom: 8px; }
.ban-notice hr { border-color: var(--border-light); margin: 24px 0; }

h1, h2, h3 { margin-bottom: 20px; font-weight: 600; }
h2 { font-size: 26px; background: linear-gradient(135deg, #fff, var(--text-secondary)); -webkit-background-clip: text; background-clip: text; color: transparent; display: inline-block; }
h3 { font-size: 18px; margin-bottom: 16px; color: var(--text-primary); }

.admin-form-group { margin-bottom: 16px; }
.admin-form-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
.admin-form-row input, .admin-form-row select { flex: 1; min-width: 140px; }

.chat-message { animation: messageAppear 0.3s ease; }
@keyframes messageAppear { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-primary); }

@media (max-width: 768px) {
    body { font-size: 16px; }
    :root { --sidebar-width: 80px; --header-height: 75px; }
    .header { padding: 0 18px; }
    .logo { font-size: 26px; }
    .user-info { padding: 6px 16px 6px 12px; }
    .user-avatar { width: 40px; height: 40px; }
    .username { font-size: 15px; }
    .sidebar { padding: 20px 10px; }
    .nav-item { padding: 14px; justify-content: center; }
    .nav-item i { font-size: 1.5rem; width: auto; }
    .nav-item span { display: none; }
    .main-content { padding: 22px 18px; }
    .card { padding: 22px; border-radius: 26px; }
    .welcome-title { font-size: 32px; }
    .welcome-text { font-size: 16px; }
    .welcome-icon { font-size: 72px; }
    .grid { grid-template-columns: 1fr; gap: 24px; }
    .media-preview { height: 180px; }
    .media-title { font-size: 18px; }
    .media-creator { font-size: 15px; }
    .btn { padding: 12px 22px; font-size: 15px; }
    h2 { font-size: 30px; }
    h3 { font-size: 20px; }
    input, textarea, select { padding: 14px 18px; font-size: 15px; border-radius: 14px; }
    label { font-size: 15px; margin-bottom: 7px; }
    .form-group { margin-bottom: 24px; }
    .profile-avatar { width: 160px; height: 160px; }
    .profile-name { font-size: 36px; }
    .profile-display-name { font-size: 20px; }
    .profile-roblox { font-size: 16px; }
    .admin-badge { font-size: 13px; padding: 5px 14px; }
    .table-container { font-size: 15px; }
    th, td { padding: 16px 14px; }
    .ban-notice { padding: 42px 28px; max-width: 90%; }
    .ban-notice i { font-size: 64px; }
    .ban-notice h1 { font-size: 32px; }
    .ban-notice p { font-size: 16px; }
}
"""

LIVE_JS = """
if (typeof FontAwesome === 'undefined') {
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';
    document.head.appendChild(link);
}
const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.card, .game-card, .media-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        observer.observe(el);
    });
});
setInterval(function(){
    fetch('/api/status').then(r => r.json()).then(d => {
        if(d.banned && d.u !== 'Mega') { window.location.href = '/banned'; }
    });
}, 3000);
"""

### --- MIDDLEWARE ---
@app.before_request
def security_check():
    db = load_db()
    u = session.get('u')
    public_routes = ['login', 'api_status', 'static', 'logout', 'banned_page', 'reset_password', 'api_messages']
    if request.endpoint in public_routes:
        return None
    if u:
        banned, ban_info = is_banned(u)
        if banned:
            session['banned'] = True
            if request.endpoint != 'banned_page':
                return redirect(url_for('banned_page'))
        user_data = db['users'].get(u, {})
        if user_data.get('must_reset_password', False):
            if request.endpoint not in ['reset_password']:
                return redirect(url_for('reset_password'))
        if u in db['users'] and not db['users'][u].get('rbx'):
            if request.endpoint not in ['link_roblox', 'reset_password']:
                return redirect(url_for('link_roblox'))

### --- ROUTES ---
@app.route('/api/status')
def api_status():
    db = load_db()
    u = session.get('u', '')
    banned, _ = is_banned(u) if u else (False, None)
    return jsonify({"u": u, "banned": banned})

@app.route('/banned')
def banned_page():
    u = session.get('u')
    if not u: return redirect(url_for('login'))
    banned, ban_info = is_banned(u)
    if not banned: return redirect(url_for('home'))
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="ban-notice"><i class="fas fa-ban"></i><h1>Account Suspended</h1><p><strong>Reason:</strong> {{ ban_info.reason }}</p><p><strong>Duration:</strong> {% if ban_info.permanent %}Permanent{% else %}Until {{ expiry_date }}{% endif %}</p><p><strong>Issued by:</strong> {{ ban_info.issued_by }}</p><p><strong>Date:</strong> {{ issued_date }}</p><hr><p>If you believe this is a mistake, please contact support.</p><a href="/logout" class="btn btn-primary" style="margin-top:24px; display:inline-block;">Return to Login</a></div><script>{{ live|safe }}</script></body></html>""", css=CSS, ban_info=ban_info,
     expiry_date=datetime.fromtimestamp(ban_info['expires']).strftime('%Y-%m-%d %H:%M:%S') if not ban_info.get('permanent') else 'N/A',
     issued_date=datetime.fromtimestamp(ban_info.get('issued_at', time.time())).strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'u' not in session: return redirect(url_for('login'))
    db = load_db()
    username = session['u']
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        if not new_password or len(new_password) < 3:
            error = "Password must be at least 3 characters long."
            return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="card" style="max-width: 450px; margin: 60px auto; text-align: center;"><i class="fas fa-key" style="font-size: 48px; color: #fbbf24; margin-bottom: 16px;"></i><h2>Reset Password</h2><p style="color: #ff6b6b; margin-bottom: 20px;">{{ error }}</p><form method="post"><div class="form-group"><input type="password" name="new_password" placeholder="New Password" required></div><div class="form-group"><input type="password" name="confirm_password" placeholder="Confirm Password" required></div><button type="submit" class="btn btn-primary" style="width:100%;">Update Password</button></form></div><script>{{ live|safe }}</script></body></html>""", css=CSS, error=error)
        if new_password != confirm_password:
            error = "Passwords do not match."
            return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="card" style="max-width: 450px; margin: 60px auto; text-align: center;"><i class="fas fa-key" style="font-size: 48px; color: #fbbf24; margin-bottom: 16px;"></i><h2>Reset Password</h2><p style="color: #ff6b6b; margin-bottom: 20px;">{{ error }}</p><form method="post"><div class="form-group"><input type="password" name="new_password" placeholder="New Password" required></div><div class="form-group"><input type="password" name="confirm_password" placeholder="Confirm Password" required></div><button type="submit" class="btn btn-primary" style="width:100%;">Update Password</button></form></div><script>{{ live|safe }}</script></body></html>""", css=CSS, error=error)
        db['users'][username]['p'] = hash_password(new_password)
        db['users'][username]['must_reset_password'] = False
        save_db(db)
        return redirect(url_for('home'))
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="card" style="max-width: 450px; margin: 60px auto; text-align: center;"><i class="fas fa-key" style="font-size: 48px; color: #fbbf24; margin-bottom: 16px;"></i><h2>Set Your Password</h2><p style="color: #9a9aae; margin-bottom: 24px;">Your account was created by an administrator. Please set a secure password.</p><form method="post"><div class="form-group"><input type="password" name="new_password" placeholder="New Password" required autofocus></div><div class="form-group"><input type="password" name="confirm_password" placeholder="Confirm Password" required></div><button type="submit" class="btn btn-primary" style="width:100%;">Set Password</button></form></div><script>{{ live|safe }}</script></body></html>""", css=CSS)

def get_layout(active):
    db = load_db()
    u = session.get('u', '')
    rbx = db['users'].get(u, {}).get('rbx')
    pfp = get_roblox_avatar_url(rbx) if rbx else DEFAULT_PROFILE_PIC
    is_user_admin = is_admin(u)
    display_name = get_display_name(u)
    header = f'''<div class="header"><div class="logo">✦ Nexus</div><div class="user-info" onclick="location.href='/profile/{u}'"><img src="{pfp}" class="user-avatar"><span class="username">{display_name}</span><i class="fas fa-chevron-down" style="font-size: 12px; color: #8b8b9e;"></i></div></div>'''
    tabs = [("/", "Dashboard", "fa-home"), ("/games", "Games", "fa-gamepad"), ("/chat", "Chat", "fa-comments"), ("/users", "Users", "fa-users"), ("/create", "Create", "fa-plus-circle")]
    if is_user_admin: tabs.insert(2, ("/admin", "Admin", "fa-crown"))
    sidebar_items = []
    for url, name, icon in tabs:
        active_class = "active" if active == name else ""
        sidebar_items.append(f'<a href="{url}" class="nav-item {active_class}"><i class="fas {icon}"></i><span>{name}</span></a>')
    sidebar = f'''<div class="sidebar">{" ".join(sidebar_items)}<div class="divider"></div><a href="/logout" class="nav-item logout-item"><i class="fas fa-sign-out-alt"></i><span>Logout</span></a></div>'''
    announcement = f'<div class="announcement"><i class="fas fa-bullhorn"></i> {db.get("ann", "") or "All systems operational"}</div>'
    return {"header": header, "sidebar": sidebar, "announcement": announcement, "db": db, "u": u, "live": LIVE_JS, "css": CSS}

@app.route('/')
def home():
    if 'u' not in session: return redirect(url_for('login'))
    c = get_layout("Dashboard")
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><div class="card welcome-card"><div class="welcome-icon"><i class="fas fa-hand-peace"></i></div><h1 class="welcome-title">Welcome back, {{ get_display_name(u) }}!</h1><p class="welcome-text">Explore games, share media, and connect with the community. Start your journey by checking out the latest games or uploading your own creations.</p></div></div></div><script>{{ live|safe }}</script></body></html>""", **c, get_display_name=get_display_name)

@app.route('/games')
def games():
    if 'u' not in session: return redirect(url_for('login'))
    c = get_layout("Games")
    games_list = []
    for idx, game in enumerate(c['db']['games']):
        games_list.append({'id': idx, 'title': game.get('title'), 'creator': game.get('creator'), 'thumb': game.get('thumb', DEFAULT_GAME_THUMB), 'creator_display': get_display_name(game.get('creator'))})
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;"><h2><i class="fas fa-gamepad"></i> All Games</h2><a href="/create" class="btn btn-primary"><i class="fas fa-plus"></i> Create Game</a></div><div class="grid">{% for g in games %}<div class="card game-card" onclick="location.href='/play/{{g.id}}'"><img src="{{g.thumb}}" class="media-preview" onerror="this.src='{{ DEFAULT_GAME_THUMB }}'"><div class="media-title">{{g.title}}</div><div class="media-creator"><i class="fas fa-user"></i> {{g.creator_display}}</div>{% if g.creator == u or is_admin(u) %}<div style="display: flex; gap: 8px; padding: 0 16px 16px 16px;"><a href="/edit/{{g.id}}" class="manage-link" onclick="event.stopPropagation()"><i class="fas fa-edit"></i> Edit</a><a href="/delete_game/{{g.id}}" class="manage-link" onclick="event.stopPropagation(); return confirm('Delete this game? This cannot be undone.')" style="color: #f87171;"><i class="fas fa-trash"></i> Delete</a></div>{% endif %}</div>{% endfor %}</div>{% if not games %}<div class="card" style="text-align:center;"><i class="fas fa-gamepad" style="font-size: 56px; color: #7cb8ff; margin-bottom: 20px;"></i><h3>No Games Yet</h3><p style="color: #9a9aae; margin-bottom: 20px;">Be the first to create a game!</p><a href="/create" class="btn btn-primary"><i class="fas fa-plus"></i> Create Game</a></div>{% endif %}</div></div><script>{{ live|safe }}</script></body></html>""", **c, games=games_list, DEFAULT_GAME_THUMB=DEFAULT_GAME_THUMB, is_admin=is_admin, get_display_name=get_display_name)

@app.route('/delete_game/<int:gid>')
def delete_game(gid):
    if 'u' not in session: return redirect(url_for('login'))
    db = load_db()
    if gid >= len(db['games']): return "Game not found", 404
    game = db['games'][gid]
    if game['creator'] != session['u'] and not is_admin(session['u']): return redirect(url_for('games'))
    db['games'].pop(gid)
    save_db(db)
    return redirect(url_for('games'))

@app.route('/profile/<name>')
def profile(name):
    if 'u' not in session: return redirect(url_for('login'))
    c = get_layout("Users")
    target = c['db']['users'].get(name)
    if not target: return "User not found", 404
    rbx = target.get('rbx')
    full_avatar = get_roblox_avatar_url(rbx) if rbx else DEFAULT_PROFILE_PIC
    is_admin_user = is_admin(name)
    display_name = get_display_name(name)
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><div class="card profile-container"><img src="{{ full_avatar }}" class="profile-avatar" onerror="this.src='{{ DEFAULT_PROFILE_PIC }}'"><div><div class="profile-name">{{ display_name }}{% if is_admin_user %}<span class="admin-badge"><i class="fas fa-crown"></i> Admin</span>{% endif %}</div><div class="profile-display-name"><i class="fas fa-at"></i> @{{ name }}</div><div class="profile-roblox"><i class="fab fa-roblox"></i> {{ t_rbx }}</div></div></div></div></div><script>{{ live|safe }}</script></body></html>""", **c, full_avatar=full_avatar, t_rbx=target.get('rbx'), name=name, display_name=display_name, DEFAULT_PROFILE_PIC=DEFAULT_PROFILE_PIC, is_admin_user=is_admin_user)

@app.route('/users')
def users():
    if 'u' not in session: return redirect(url_for('login'))
    c = get_layout("Users")
    user_list = []
    for name, data in c['db']['users'].items():
        banned, _ = is_banned(name)
        rbx = data.get('rbx')
        pfp = get_roblox_avatar_url(rbx) if rbx else DEFAULT_PROFILE_PIC
        user_list.append({'name': name, 'display_name': get_display_name(name), 'pfp': pfp, 'banned': banned, 'is_admin': is_admin(name)})
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><h2><i class="fas fa-users"></i> Community</h2><div class="grid">{% for usr in user_list %}<div class="card game-card" onclick="location.href='/profile/{{usr.name}}'"><img src="{{usr.pfp}}" class="media-preview" onerror="this.src='{{ DEFAULT_PROFILE_PIC }}'"><div class="media-title">{{usr.display_name}}{% if usr.is_admin %}<span class="admin-badge"><i class="fas fa-crown"></i> Admin</span>{% endif %}</div><div class="media-creator"><i class="fas fa-at"></i> @{{usr.name}}</div>{% if usr.banned %}<div style="color: #f87171; font-weight: 500;">Suspended</div>{% endif %}</div>{% endfor %}</div></div></div><script>{{ live|safe }}</script></body></html>""", **c, user_list=user_list, DEFAULT_PROFILE_PIC=DEFAULT_PROFILE_PIC)

@app.route('/link_roblox', methods=['GET', 'POST'])
def link_roblox():
    if 'u' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        rbx = request.form.get('rbx_user').strip()
        if rbx:
            db = load_db()
            db['users'][session['u']]['rbx'] = rbx
            save_db(db)
            return redirect(url_for('home'))
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="card" style="max-width: 450px; margin: 60px auto; text-align: center;"><i class="fab fa-roblox" style="font-size: 56px; color: #00a2ff; margin-bottom: 20px;"></i><h2>Connect Roblox</h2><p style="color: #9a9aae; margin-bottom: 32px;">Enter your Roblox username to continue</p><form method="post"><div class="form-group"><input type="text" name="rbx_user" placeholder="Roblox Username" required></div><button type="submit" class="btn btn-primary" style="width:100%;">Connect</button></form></div><script>{{ live|safe }}</script></body></html>""", css=CSS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u', '').strip(), request.form.get('p', '').strip()
        d = load_db()
        banned, ban_info = is_banned(u)
        if banned:
            return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="ban-notice"><i class="fas fa-ban"></i><h1>Suspended</h1><p><strong>Reason:</strong> {{ reason }}</p><a href="/" class="btn btn-primary" style="text-decoration: none;">Return</a></div><script>{{ live|safe }}</script></body></html>""", css=CSS, reason=ban_info['reason'])
        if u in d['users']:
            stored_password = d['users'][u]['p']
            if len(stored_password) == 64 and all(c in '0123456789abcdef' for c in stored_password):
                if stored_password == hash_password(p):
                    session.permanent = True
                    session['u'] = u
                    if d['users'][u].get('must_reset_password', False): return redirect(url_for('reset_password'))
                    return redirect(url_for('home'))
            else:
                if stored_password == p:
                    d['users'][u]['p'] = hash_password(p)
                    save_db(d)
                    session.permanent = True
                    session['u'] = u
                    if d['users'][u].get('must_reset_password', False): return redirect(url_for('reset_password'))
                    return redirect(url_for('home'))
        elif u not in d['users'] and u != "":
            d['users'][u] = {"p": hash_password(p), "rbx": None, "must_reset_password": False, "display_name": u, "avatar_file": None}
            save_db(d)
            session.permanent = True
            session['u'] = u
            return redirect(url_for('home'))
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body style="justify-content:center; align-items:center;"><div class="card" style="max-width: 420px; margin: 60px auto; text-align: center;"><i class="fas fa-gem" style="font-size: 56px; color: #7cb8ff; margin-bottom: 20px;"></i><h2>Welcome</h2><p style="color:#9a9aae; margin-bottom: 32px;">Sign in to your account</p><form method="post"><div class="form-group"><input name="u" placeholder="Username" required></div><div class="form-group"><input type="password" name="p" placeholder="Password" required></div><button type="submit" class="btn btn-primary" style="width:100%;">Sign In</button></form></div><script>{{ live|safe }}</script></body></html>""", css=CSS)

@app.route('/create', methods=['GET', 'POST'])
@app.route('/edit/<int:gid>', methods=['GET', 'POST'])
def create_edit(gid=None):
    if 'u' not in session: return redirect(url_for('login'))
    c = get_layout("Create")
    g = None
    if gid is not None and gid < len(c['db']['games']):
        g = c['db']['games'][gid].copy()
        g['id'] = gid
        if g['creator'] != session['u'] and not is_admin(session['u']): return redirect(url_for('home'))
    if request.method == 'POST':
        new_g = {"title": request.form.get('t'), "creator": session['u'], "thumb": request.form.get('i') or DEFAULT_GAME_THUMB, "code": request.form.get('c'), "plays": g.get('plays', 0) if g else 0, "likes": g.get('likes', 0) if g else 0, "liked_by": g.get('liked_by', []) if g else []}
        if gid is not None and g: c['db']['games'][gid] = new_g
        else: c['db']['games'].append(new_g)
        save_db(c['db'])
        return redirect(url_for('games'))
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><h2><i class="fas fa-edit"></i> {% if g %}Edit Game{% else %}Create Game{% endif %}</h2><div class="card"><form method="post"><div class="form-group"><label>Game Title</label><input name="t" value="{{ g.title if g else '' }}" required></div><div class="form-group"><label>Thumbnail URL</label><input name="i" value="{{ g.thumb if g else '' }}" placeholder="https://..."><small style="color:#9a9aae;">Leave empty for default thumbnail</small></div><div class="form-group"><label>Game Code (HTML/CSS/JS)</label><textarea name="c" rows="20">{{ g.code if g else '' }}</textarea><small style="color:#9a9aae;">Paste your game's HTML/CSS/JS code here</small></div><div style="display: flex; gap: 12px; flex-wrap: wrap;"><button type="submit" class="btn btn-primary">Save Game</button><a href="/games" class="btn btn-secondary" style="text-decoration: none;">Cancel</a></div></form></div></div></div><script>{{ live|safe }}</script></body></html>""", **c, g=g)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not is_admin(session.get('u')): return redirect(url_for('home'))
    c = get_layout("Admin")
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create_user':
            username = request.form.get('new_username', '').strip()
            if username and username not in c['db']['users']:
                random_password = generate_random_password(8)
                c['db']['users'][username] = {"p": hash_password(random_password), "rbx": None, "must_reset_password": True, "display_name": username, "avatar_file": None}
                save_db(c['db'])
                session['last_created_password'] = random_password
                session['last_created_user'] = username
            return redirect(url_for('admin'))
        elif action == 'update_display_name':
            username = request.form.get('display_name_user', '').strip()
            new_display_name = request.form.get('new_display_name', '').strip()
            if username and username in c['db']['users'] and new_display_name:
                c['db']['users'][username]['display_name'] = new_display_name
                save_db(c['db'])
                session['display_name_updated'] = username
            return redirect(url_for('admin'))
        elif action == 'add_admin':
            username = request.form.get('admin_username', '').strip()
            if username and username in c['db']['users']:
                admins = c['db'].get('admins', [])
                if username not in admins:
                    admins.append(username)
                    c['db']['admins'] = admins
                    save_db(c['db'])
                    session['admin_added'] = username
            return redirect(url_for('admin'))
        elif action == 'remove_admin':
            username = request.form.get('remove_admin_username', '').strip()
            if username and username in c['db'].get('admins', []):
                admins = c['db'].get('admins', [])
                if username in admins:
                    admins.remove(username)
                    c['db']['admins'] = admins
                    save_db(c['db'])
                    session['admin_removed'] = username
            return redirect(url_for('admin'))
        elif action == 'ban':
            username = request.form.get('ban_user')
            reason = request.form.get('ban_reason')
            duration = request.form.get('ban_duration')
            duration_value = int(request.form.get('ban_duration_value', 0))
            if username and username in c['db']['users']:
                bans = c['db'].get('bans', {})
                expires = 0
                permanent = False
                if duration == 'permanent': permanent = True
                elif duration == 'hours': expires = time.time() + (duration_value * 3600)
                elif duration == 'days': expires = time.time() + (duration_value * 86400)
                elif duration == 'weeks': expires = time.time() + (duration_value * 604800)
                bans[username] = {'reason': reason, 'permanent': permanent, 'expires': expires, 'issued_by': session.get('u'), 'issued_at': time.time()}
                c['db']['bans'] = bans
                save_db(c['db'])
            return redirect(url_for('admin'))
        elif action == 'unban':
            username = request.form.get('unban_user')
            if username and username in c['db'].get('bans', {}):
                del c['db']['bans'][username]
                save_db(c['db'])
            return redirect(url_for('admin'))
        elif 'a' in request.form:
            c['db']['ann'] = request.form.get('a', '')
            save_db(c['db'])
            return redirect(url_for('admin'))
    last_password = session.pop('last_created_password', None)
    last_user = session.pop('last_created_user', None)
    admin_added = session.pop('admin_added', None)
    admin_removed = session.pop('admin_removed', None)
    display_name_updated = session.pop('display_name_updated', None)
    users_list = []
    for username, user_data in c['db']['users'].items():
        banned, _ = is_banned(username)
        users_list.append({'name': username, 'display_name': user_data.get('display_name', username), 'banned': banned, 'must_reset': user_data.get('must_reset_password', False), 'is_admin': username in c['db'].get('admins', [])})
    current_admins = c['db'].get('admins', [])
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><h2><i class="fas fa-crown"></i> Admin Panel</h2><div class="card"><h3><i class="fas fa-user-plus"></i> Create User</h3><form method="post"><input type="hidden" name="action" value="create_user"><div class="admin-form-group"><input type="text" name="new_username" placeholder="Username" required style="width: 100%;"></div><button type="submit" class="btn btn-success">Create Account</button></form></div>{% if last_password and last_user %}<div class="card" style="border: 1px solid #3fb950;"><h3><i class="fas fa-check-circle"></i> User Created</h3><p><strong>{{ last_user }}</strong></p><p>Password: <code style="background: #1a1a24; padding: 4px 8px; border-radius: 8px;">{{ last_password }}</code></p><p style="color: #fbbf24; margin-top: 8px;">⚠️ User must reset password on first login.</p></div>{% endif %}{% if display_name_updated %}<div class="card" style="border: 1px solid #7cb8ff;"><h3><i class="fas fa-user-edit"></i> Display Name Updated</h3><p><strong>{{ display_name_updated }}</strong>'s display name has been updated.</p></div>{% endif %}{% if admin_added %}<div class="card" style="border: 1px solid #7cb8ff;"><h3><i class="fas fa-user-shield"></i> Admin Added</h3><p><strong>{{ admin_added }}</strong> is now an administrator.</p></div>{% endif %}{% if admin_removed %}<div class="card" style="border: 1px solid #ff6b6b;"><h3><i class="fas fa-user-minus"></i> Admin Removed</h3><p><strong>{{ admin_removed }}</strong> is no longer an administrator.</p></div>{% endif %}<div class="card"><h3><i class="fas fa-user-edit"></i> Update Display Name</h3><form method="post"><input type="hidden" name="action" value="update_display_name"><div class="admin-form-group"><input type="text" name="display_name_user" placeholder="Username" required style="width: 100%;"></div><div class="admin-form-group"><input type="text" name="new_display_name" placeholder="New Display Name" required style="width: 100%;"></div><button type="submit" class="btn btn-primary"><i class="fas fa-pen"></i> Update Display Name</button></form></div><div class="card"><h3><i class="fas fa-user-shield"></i> Manage Admins</h3><div style="display: flex; gap: 20px; flex-wrap: wrap;"><form method="post" style="flex: 1;"><input type="hidden" name="action" value="add_admin"><div class="admin-form-group"><input type="text" name="admin_username" placeholder="Username to add as admin" required style="width: 100%;"></div><button type="submit" class="btn btn-primary"><i class="fas fa-plus"></i> Add Admin</button></form><form method="post" style="flex: 1;"><input type="hidden" name="action" value="remove_admin"><div class="admin-form-group"><input type="text" name="remove_admin_username" placeholder="Username to remove from admin" required style="width: 100%;"></div><button type="submit" class="btn btn-danger"><i class="fas fa-trash"></i> Remove Admin</button></form></div>{% if current_admins %}<div style="margin-top: 16px;"><strong>Current Admins:</strong><div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;">{% for admin in current_admins %}<span style="background: rgba(124, 184, 255, 0.15); padding: 4px 12px; border-radius: 20px;"><i class="fas fa-crown" style="color: #7cb8ff;"></i> {{ admin }}</span>{% endfor %}</div></div>{% endif %}</div><div class="card"><h3><i class="fas fa-bullhorn"></i> Announcement</h3><form method="post"><div class="admin-form-group"><input type="text" name="a" value="{{db.ann}}" placeholder="Announcement text" style="width: 100%;"></div><button type="submit" class="btn btn-primary">Update Announcement</button></form></div><div class="card"><h3><i class="fas fa-gavel"></i> Ban User</h3><form method="post"><input type="hidden" name="action" value="ban"><div class="admin-form-group"><input type="text" name="ban_user" placeholder="Username" required style="width: 100%;"></div><div class="admin-form-group"><input type="text" name="ban_reason" placeholder="Reason" required style="width: 100%;"></div><div class="admin-form-row"><select name="ban_duration"><option value="hours">Hours</option><option value="days">Days</option><option value="weeks">Weeks</option><option value="permanent">Permanent</option></select><input type="number" name="ban_duration_value" placeholder="Duration" value="1"><button type="submit" class="btn btn-danger">Ban User</button></div></form></div><div class="card"><h3><i class="fas fa-unlock-alt"></i> Unban User</h3><form method="post"><input type="hidden" name="action" value="unban"><div class="admin-form-group"><input type="text" name="unban_user" placeholder="Username" required style="width: 100%;"></div><button type="submit" class="btn btn-primary">Unban User</button></form></div><div class="card"><h3><i class="fas fa-list"></i> User List</h3><div class="table-container"><table><thead><tr><th>Username</th><th>Display Name</th><th>Status</th><th>Admin</th><th>Password</th></tr></thead><tbody>{% for user in users_list %}<tr><td><strong>@{{user.name}}</strong></td><td>{{user.display_name}}</td><td>{% if user.banned %}<span class="status-banned">Banned</span>{% else %}<span class="status-active">Active</span>{% endif %}</td><td>{% if user.is_admin %}<span class="status-admin"><i class="fas fa-crown"></i> Admin</span>{% else %}—{% endif %}</td><td>{% if user.must_reset %}<span style="color: #fbbf24;">Reset Required</span>{% else %}<span style="color: #3fb950;">Set</span>{% endif %}</td></tr>{% endfor %}</tbody></table></div></div></div></div><script>{{ live|safe }}</script></body></html>""",
        **c, users_list=users_list, last_password=last_password, last_user=last_user, admin_added=admin_added, admin_removed=admin_removed, display_name_updated=display_name_updated, current_admins=current_admins)

@app.route('/play/<int:gid>')
def play(gid):
    db = load_db()
    if gid >= len(db['games']): return "Game not found", 404
    game = db['games'][gid]
    game['plays'] = game.get('plays', 0) + 1
    save_db(db)
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>*{margin:0;padding:0;box-sizing:border-box;}body{background:#0f0f13;}.game-bar{position:fixed;top:0;left:0;right:0;background:rgba(18,18,24,0.98);backdrop-filter:blur(12px);padding:14px 28px;display:flex;justify-content:space-between;align-items:center;z-index:100;border-bottom:1px solid rgba(255,255,255,0.06);animation:slideInUp 0.5s ease;}.game-title{font-size:16px;font-weight:600;color:#ffffff;}.back-btn{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);padding:8px 20px;border-radius:40px;color:white;cursor:pointer;font-size:14px;font-weight:500;transition:all 0.3s ease;text-decoration:none;}.back-btn:hover{background:rgba(255,255,255,0.15);transform:scale(1.05);text-decoration:none;}@keyframes slideInUp{from{opacity:0;transform:translateY(-30px);}to{opacity:1;transform:translateY(0);}}#game-frame{width:100%;height:100vh;border:none;background:#0f0f13;}</style></head><body><div class="game-bar"><span class="game-title"><i class="fas fa-gamepad" style="margin-right:8px;"></i>{{ game.title }}</span><button class="back-btn" onclick="location.href='/games'"><i class="fas fa-arrow-left"></i> Exit Game</button></div><iframe id="game-frame" srcdoc='{{ game.code|e }}' sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-modals allow-fullscreen" style="margin-top:55px;height:calc(100vh - 55px);"></iframe><script>{{ live|safe }}</script></body></html>""", game=game)

@app.route('/chat')
def chat():
    if 'u' not in session: return redirect(url_for('login'))
    c = get_layout("Chat")
    messages = c['db'].get('messages', [])[-10:]
    return render_template_string("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes"><style>{{ css }}</style><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"></head><body>{{ header|safe }}{{ announcement|safe }}<div class="layout">{{ sidebar|safe }}<div class="main-content"><h2><i class="fas fa-comments"></i> Chat</h2><div class="card"><div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 12px; margin-bottom: 16px; font-size: 14px; color: #7cb8ff;"><i class="fas fa-info-circle"></i> <strong>Chat Info:</strong> This chat updates automatically every 3 seconds. While typing, updates pause to avoid interrupting your message composition.</div><div id="chat-messages" style="height: 400px; overflow-y: auto; padding: 16px; background: rgba(20,20,28,0.5); border-radius: 16px; margin-bottom: 16px;">{% for msg in messages %}<div class="chat-message" data-timestamp="{{msg.timestamp}}"><div style="margin-bottom:12px; padding:8px 12px; background: rgba(30,30,40,0.7); border-radius:8px; display:flex; align-items:flex-start;"><img src="{{ get_pfp(msg.user) }}" style="width:30px; height:30px; border-radius:50%; margin-right:10px;" onerror="this.src='{{ DEFAULT_PROFILE_PIC }}'"><div><div style="display:flex; align-items:baseline; gap:8px;"><strong style="color:#7cb8ff;">{{ get_display_name(msg.user) }}</strong><span style="font-size:0.8em; color:#8b8b9e;">{{ msg.timestamp }}</span></div><div style="margin-top:4px; line-height:1.4;">{{ msg.text }}</div></div></div></div>{% endfor %}{% if not messages %}<div style="text-align:center; color:#8b8b9e; padding:20px;">No messages yet. Be the first to chat!</div>{% endif %}</div><form method="post" action="/send_message" style="display:flex; gap:8px;" id="chatForm"><input type="text" name="message" id="messageInput" placeholder="Type your message..." required style="flex:1; padding:12px 16px; background:rgba(20,20,28,0.9); border:1px solid rgba(255,255,255,0.08); border-radius:16px; color:#e0e0e8;"><button type="submit" class="btn btn-primary" style="white-space:nowrap;"><i class="fas fa-paper-plane"></i> Send</button></form></div></div></div><script>let isTyping=false;let refreshInterval;let lastTimestamp=null;const messageElements=document.querySelectorAll('.chat-message');if(messageElements.length>0){lastTimestamp=Array.from(messageElements).map(el=>el.getAttribute('data-timestamp')).sort().pop();}document.getElementById('messageInput').addEventListener('focus',()=>{isTyping=true;});document.getElementById('messageInput').addEventListener('blur',()=>{setTimeout(()=>{isTyping=false;},1000);});function updateMessages(){if(!isTyping){fetch('/api/messages?since='+encodeURIComponent(lastTimestamp||'')).then(r=>r.json()).then(data=>{if(data.new_messages&&data.new_messages.length>0){const chatContainer=document.getElementById('chat-messages');data.new_messages.forEach(msg=>{const div=document.createElement('div');div.className='chat-message';div.setAttribute('data-timestamp',msg.timestamp);div.innerHTML=`<div style="margin-bottom:12px; padding:8px 12px; background: rgba(30,30,40,0.7); border-radius:8px; display:flex; align-items:flex-start;"><img src="${msg.pfp}" style="width:30px; height:30px; border-radius:50%; margin-right:10px;" onerror="this.src='{{ DEFAULT_PROFILE_PIC }}'"><div><div style="display:flex; align-items:baseline; gap:8px;"><strong style="color:#7cb8ff;">${msg.display_name}</strong><span style="font-size:0.8em; color:#8b8b9e;">${msg.timestamp}</span></div><div style="margin-top:4px; line-height:1.4;">${msg.text}</div></div></div>`;chatContainer.appendChild(div);});lastTimestamp=data.last_timestamp;chatContainer.scrollTop=chatContainer.scrollHeight;}}).catch(err=>console.log('Update failed:',err));}}refreshInterval=setInterval(updateMessages,3000);document.getElementById('chatForm').addEventListener('submit',function(e){clearInterval(refreshInterval);});function scrollToBottom(){const chatMessages=document.getElementById('chat-messages');chatMessages.scrollTop=chatMessages.scrollHeight;}scrollToBottom();</script><script>{{ live|safe }}</script></body></html>""", **c, messages=messages, get_display_name=get_display_name, get_pfp=get_pfp, DEFAULT_PROFILE_PIC=DEFAULT_PROFILE_PIC)

@app.route('/api/messages')
def api_messages():
    if 'u' not in session: return jsonify({'error': 'Not logged in'}), 401
    since_timestamp = request.args.get('since', type=str)
    db = load_db()
    all_messages = db.get('messages', [])
    if since_timestamp:
        try:
            since_time = datetime.strptime(since_timestamp, "%Y-%m-%d %H:%M:%S")
            new_messages = []
            for msg in all_messages:
                msg_time = datetime.strptime(msg['timestamp'], "%Y-%m-%d %H:%M:%S")
                if msg_time > since_time:
                    msg_with_info = msg.copy()
                    msg_with_info['display_name'] = get_display_name(msg['user'])
                    msg_with_info['pfp'] = get_pfp(msg['user'])
                    new_messages.append(msg_with_info)
        except ValueError:
            new_messages = [{'display_name': get_display_name(m['user']), 'pfp': get_pfp(m['user']), **m} for m in all_messages]
    else:
        new_messages = [{'display_name': get_display_name(m['user']), 'pfp': get_pfp(m['user']), **m} for m in all_messages]
    last_timestamp = since_timestamp
    if new_messages:
        timestamps = [datetime.strptime(m['timestamp'], "%Y-%m-%d %H:%M:%S") for m in new_messages]
        last_timestamp = max(timestamps).strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({'new_messages': new_messages, 'last_timestamp': last_timestamp})

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'u' not in session: return redirect(url_for('login'))
    message_text = request.form.get('message', '').strip()
    if not message_text: return redirect(url_for('chat'))
    try:
        db = load_db()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = {"user": session['u'], "text": message_text, "timestamp": timestamp}
        db['messages'].append(message)
        db['messages'] = db['messages'][-100:]
        save_db(db)
    except Exception as e:
        print(f"Error saving message: {e}")
    return redirect(url_for('chat'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    db = load_db()
    if 'Mega' in db.get('users', {}) and 'Mega' not in db.get('admins', []):
        db['admins'].append('Mega')
        save_db(db)
    print("📌 Mega added as default admin")
    import sys
    debug_mode = '--debug' in sys.argv
    port = int(os.environ.get("PORT", 3000))
    print(f"🚀 Starting server on port {port} (debug={debug_mode})...")
    app.run(debug=debug_mode, port=port, host='0.0.0.0')
