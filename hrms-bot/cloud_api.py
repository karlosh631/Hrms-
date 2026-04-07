"""
cloud_api.py – Optional lightweight HTTP API for headless / cloud / mobile operation.

Start with:   python cloud_api.py
Or via main:  HRMS_CLOUD_MODE=true python main.py

Endpoints
---------
GET  /           → simple HTML dashboard (works from a mobile browser)
GET  /api/status → JSON  { date, permission, tasks }
POST /api/permission  body: { "enabled": true|false }
POST /api/clock-in
POST /api/clock-out
"""
import logging
import threading
from datetime import date

logger = logging.getLogger(__name__)

try:
    from flask import Flask, jsonify, request, render_template_string  # type: ignore
    _FLASK_AVAILABLE = True
except ImportError:
    _FLASK_AVAILABLE = False
    logger.warning("Flask not installed – cloud API unavailable.  pip install flask")


# ── HTML template ──────────────────────────────────────────────────────────

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>HRMS Bot – Dashboard</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#1e2a45;color:#fff;
         display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
    .card{background:#fff;color:#2c3e50;border-radius:16px;padding:36px;
          max-width:420px;width:100%;box-shadow:0 12px 48px rgba(0,0,0,.4)}
    h1{font-size:1.6rem;margin-bottom:4px}
    .sub{color:#7f8c8d;font-size:.9rem;margin-bottom:24px}
    .badge{display:inline-block;padding:4px 12px;border-radius:20px;
           font-size:.8rem;font-weight:700}
    .green{background:#d5f5e3;color:#1e8449}
    .red{background:#fde8e8;color:#c0392b}
    .yellow{background:#fef5e7;color:#d68910}
    .section{margin-bottom:20px}
    .section h2{font-size:1rem;margin-bottom:8px;color:#7f8c8d;
                text-transform:uppercase;letter-spacing:.5px}
    .row{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}
    button{flex:1;padding:14px;border:none;border-radius:10px;font-size:1rem;
           font-weight:700;cursor:pointer;color:#fff}
    .btn-yes{background:#27ae60}
    .btn-no{background:#e74c3c}
    .btn-in{background:#4f8ef7}
    .btn-out{background:#f39c12}
    button:active{opacity:.8}
    .log{font-size:.82rem;color:#555;background:#f8f9fa;border-radius:8px;
         padding:12px;max-height:160px;overflow-y:auto}
    .msg{margin-top:16px;font-size:.9rem;color:#27ae60;min-height:20px}
  </style>
</head>
<body>
<div class="card">
  <h1>🤖 HRMS Bot</h1>
  <p class="sub">Auto Attendance Controller</p>

  <div class="section">
    <h2>Today's Permission</h2>
    <span id="perm-badge" class="badge yellow">Loading …</span>
    <div class="row">
      <button class="btn-yes" onclick="setPermission(true)">✅ Enable Today</button>
      <button class="btn-no"  onclick="setPermission(false)">❌ Disable Today</button>
    </div>
  </div>

  <div class="section">
    <h2>Manual Actions</h2>
    <div class="row">
      <button class="btn-in"  onclick="doAction('clock-in')">▶ Clock In Now</button>
      <button class="btn-out" onclick="doAction('clock-out')">■ Clock Out Now</button>
    </div>
  </div>

  <div class="section">
    <h2>Today's Log</h2>
    <div class="log" id="log">Loading …</div>
  </div>

  <div class="msg" id="msg"></div>
</div>

<script>
async function api(path, method='GET', body=null){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(body) opts.body=JSON.stringify(body);
  const r=await fetch(path,opts);
  return r.json();
}

async function refresh(){
  const d=await api('/api/status');
  const p=d.permission;
  const badge=document.getElementById('perm-badge');
  if(p===true){badge.textContent='ENABLED ✅';badge.className='badge green';}
  else if(p===false){badge.textContent='DISABLED ❌';badge.className='badge red';}
  else{badge.textContent='Pending …';badge.className='badge yellow';}
  const log=document.getElementById('log');
  if(d.tasks && d.tasks.length){
    log.innerHTML=d.tasks.map(t=>
      `<div>${t.action_type} | <b>${t.status}</b> | retries:${t.retry_count}</div>`
    ).join('');
  } else {log.textContent='No tasks yet.';}
}

async function setPermission(enabled){
  const d=await api('/api/permission','POST',{enabled});
  document.getElementById('msg').textContent=d.message||'Done';
  refresh();
}

async function doAction(action){
  const d=await api(`/api/${action}`,'POST');
  document.getElementById('msg').textContent=d.message||'Triggered';
}

refresh();
setInterval(refresh, 15000);
</script>
</body>
</html>"""


# ── Flask app factory ──────────────────────────────────────────────────────

def create_cloud_app(scheduler, storage):
    if not _FLASK_AVAILABLE:
        return None

    app = Flask(__name__)
    app.logger.setLevel(logging.WARNING)  # silence Flask access log noise

    @app.route("/")
    def index():
        return render_template_string(_DASHBOARD_HTML)

    @app.route("/api/status")
    def status():
        perm  = storage.get_today_permission()
        tasks = storage.get_today_tasks()
        return jsonify({
            "date":       date.today().isoformat(),
            "permission": perm,
            "tasks":      tasks,
        })

    @app.route("/api/permission", methods=["POST"])
    def set_permission():
        data    = request.get_json(force=True, silent=True) or {}
        enabled = bool(data.get("enabled", True))
        storage.set_today_permission(enabled)
        return jsonify({
            "status":  "ok",
            "enabled": enabled,
            "message": f"Permission {'granted ✅' if enabled else 'denied ❌'} for today.",
        })

    @app.route("/api/clock-in", methods=["POST"])
    def manual_clock_in():
        scheduler.manual_clock_in()
        return jsonify({"status": "ok", "message": "Clock-in triggered in background."})

    @app.route("/api/clock-out", methods=["POST"])
    def manual_clock_out():
        scheduler.manual_clock_out()
        return jsonify({"status": "ok", "message": "Clock-out triggered in background."})

    return app


def run_cloud_api(scheduler, storage, port: int = 8080) -> None:
    """Start the Flask dev server in a daemon thread."""
    app = create_cloud_app(scheduler, storage)
    if app is None:
        logger.warning("Flask unavailable – cloud API not started.")
        return

    def _run():
        logger.info("Cloud API listening on http://0.0.0.0:%d", port)
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="cloud-api")
    t.start()
