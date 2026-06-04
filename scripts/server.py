#!/usr/bin/env python3
"""Secure storage report server with guarded delete API.

SAFETY:
- Binds 127.0.0.1 only (no network exposure)
- Random per-session token required for all POST
- All paths realpath-canonicalized, verified against allowlist
- Only paths within allowlist + HOME are accepted
- Host header must be 127.0.0.1 (blocks DNS rebinding)

Usage: server.py <analysis.json>
"""
import json, os, secrets, shutil, subprocess, sys, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "assets", "report_template_enhanced.html")
HOME = os.path.realpath(os.path.expanduser("~"))
TOKEN = secrets.token_urlsafe(32)  # 256-bit random

DATA = {}; TPL_CONTENT = ""
RM_ALLOW = set(); TRASH_ALLOW = set(); OPEN_ALLOW = set()
PROTECTED = {  # Never delete these
    os.path.realpath("C:\\Windows"), os.path.realpath("C:\\Program Files"),
    os.path.realpath("C:\\Program Files (x86)"), os.path.realpath("/bin"),
    os.path.realpath("/etc"), os.path.realpath("/usr"),
    os.path.realpath("/System"), os.path.realpath("/Applications"),
}

def rpath(p):
    """Realpath + home expansion, returns canonical absolute path."""
    return os.path.realpath(os.path.expanduser(p))

def load(src):
    data = {}
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(TPL, "r", encoding="utf-8") as f:
        tpl = f.read()
    rm_a, tr_a, op_a = set(), set(), set()
    for it in data.get("green", []):
        for p in (it.get("trash_paths") or []):
            rp = rpath(p)
            if rp not in PROTECTED:
                rm_a.add(rp); tr_a.add(rp); op_a.add(rp)
    for it in data.get("yellow", []):
        for p in (it.get("trash_paths") or []):
            rp = rpath(p)
            if rp not in PROTECTED:
                tr_a.add(rp); op_a.add(rp)
        if it.get("path"):
            rp = rpath(it["path"])
            if os.path.exists(rp) and rp not in PROTECTED:
                op_a.add(rp)
    return data, tpl, rm_a, tr_a, op_a

def move_to_trash(path):
    """Cross-platform move to trash."""
    plat = sys.platform
    if plat == "darwin":
        script = 'tell application "Finder" to delete (POSIX file %s as alias)' % json.dumps(path)
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode != 0:
            dest = os.path.join(HOME, ".Trash", os.path.basename(path.rstrip("/")) + "." + time.strftime("%H%M%S"))
            shutil.move(path, dest)
    elif plat.startswith("win"):
        import ctypes; from ctypes import wintypes
        class SF(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16),
                        ("fAborted", wintypes.BOOL), ("hMappings", ctypes.c_void_p),
                        ("lpszTitle", wintypes.LPCWSTR)]
        op = SF(); op.wFunc = 3; op.pFrom = os.path.abspath(path) + "\x00\x00"
        op.fFlags = 0x0040 | 0x0010 | 0x0004  # ALLOWUNDO | NOCONFIRM | SILENT
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc != 0: raise OSError(f"SHFileOperation failed (code {rc})")
    else:
        # Linux XDG trash
        td = os.path.expanduser("~/.local/share/Trash")
        fd = os.path.join(td, "files"); os.makedirs(fd, exist_ok=True)
        bn = os.path.basename(path.rstrip("/"))
        dest = os.path.join(fd, bn); c = 1
        while os.path.exists(dest): dest = os.path.join(fd, f"{bn}.{c}"); c += 1
        shutil.move(path, dest)

def hard_delete(path):
    if os.path.isdir(path) and not os.path.islink(path): shutil.rmtree(path)
    else: os.remove(path)

def open_in_manager(target):
    plat = sys.platform
    if plat == "darwin": subprocess.run(["open", "-R", target], capture_output=True)
    elif plat.startswith("win"): subprocess.run(["explorer", target])
    else: subprocess.run(["xdg-open", os.path.dirname(target) if os.path.isfile(target) else target], capture_output=True)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            blob = json.dumps(DATA, ensure_ascii=False)
            cfg = json.dumps({"token": TOKEN, "endpoint": "/action"})
            html = TPL_CONTENT.replace("__REPORT_DATA__", blob).replace("__DELETE_CONFIG__", cfg)
            self._send(200, html, "text/html; charset=utf-8")
        else:
            self._send(404, '{"ok":false,"error":"not found"}')

    def do_POST(self):
        if self.path != "/action":
            self._send(404, json.dumps({"ok": False, "error": "not found"})); return
        # DNS rebinding guard
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self._send(403, json.dumps({"ok": False, "error": "invalid host"})); return
        # Read body
        n = int(self.headers.get("Content-Length", 0))
        try: req = json.loads(self.rfile.read(n) or "{}")
        except: self._send(400, json.dumps({"ok": False, "error": "bad json"})); return
        if req.get("token") != TOKEN:
            self._send(403, json.dumps({"ok": False, "error": "invalid token"})); return

        mode = req.get("mode")
        allow = {"rm": RM_ALLOW, "trash": TRASH_ALLOW, "open": OPEN_ALLOW}.get(mode)
        if allow is None:
            self._send(400, json.dumps({"ok": False, "error": "unknown mode"})); return

        done = []
        for p in (req.get("paths") or []):
            rp = rpath(p)
            # Path traversal check
            if rp not in allow:
                self._send(403, json.dumps({"ok": False, "error": f"not in allowlist: {p}"})); return
            # Only allow paths under HOME
            if not (rp == HOME or rp.startswith(HOME + os.sep)):
                self._send(403, json.dumps({"ok": False, "error": f"out of bounds: {p}"})); return
            # Protected paths check
            if any(rp == pp or rp.startswith(pp + os.sep) for pp in PROTECTED):
                self._send(403, json.dumps({"ok": False, "error": f"protected path: {p}"})); return
            try:
                if mode == "open": open_in_manager(rp)
                elif not os.path.exists(rp): pass
                elif mode == "trash": move_to_trash(rp)
                else: hard_delete(rp)
                done.append(p)
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": str(e)})); return
        self._send(200, json.dumps({"ok": True, "done": done}))

def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    global DATA, TPL_CONTENT, RM_ALLOW, TRASH_ALLOW, OPEN_ALLOW
    DATA, TPL_CONTENT, RM_ALLOW, TRASH_ALLOW, OPEN_ALLOW = load(sys.argv[1])
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # localhost only
    port = srv.server_address[1]
    print(f"Server: http://127.0.0.1:{port}/  (token: {TOKEN[:8]}...)")
    print(f"  Deletable: {len(RM_ALLOW)} items | Ctrl+C to stop")
    webbrowser.open(f"http://127.0.0.1:{port}/")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nServer stopped.")

if __name__ == "__main__": main()
