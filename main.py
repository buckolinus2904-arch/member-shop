"""Backend: SellAuth -> redeem page -> VaultCord marketplace (buy + pull). Runs on Vercel."""
import hashlib, hmac, html, json, math, os, re, secrets, time
import httpx
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

# All secrets come from environment variables (Vercel: Settings -> Environment Variables).
VC_KEY = os.environ["VAULTCORD_API_KEY"]
ADMIN_TOKEN = os.environ["ADMIN_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
SELLAUTH_SECRET = os.environ.get("SELLAUTH_WEBHOOK_SECRET", "")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
BRAND = os.environ.get("BRAND_NAME", "Your Shop")
SUPPORT_URL = os.environ.get("SUPPORT_URL", "#")

OFFERS = {
    "standard": {"market_id": 3271, "cents_per_100": 8, "min": 1, "max": 4000},
    "valid": {"market_id": 3248, "cents_per_100": 10, "min": 1000, "max": 4000},
}
BUDGET_BUFFER = 1.10
INVITE_RE = re.compile(
    r"^(?:https?://)?(?:discord\.gg/|discord(?:app)?\.com/invite/)([\w-]+)/?$"
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = FastAPI()


# ---------- Database ----------
def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


with db() as _c:
    _c.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            code TEXT PRIMARY KEY,
            tier TEXT,
            amount INT,
            status TEXT DEFAULT 'new',
            email TEXT,
            invite_link TEXT,
            order_id TEXT,
            bot_url TEXT,
            cost INT,
            error TEXT,
            created_at BIGINT
        )
    """)


def get(code):
    with db() as c:
        return c.execute(
            "SELECT * FROM orders WHERE code=%s", (code,)
        ).fetchone()


def update(code, **f):
    allowed = {
        "status", "email", "invite_link", "order_id",
        "bot_url", "cost", "error"
    }
    if not f or not set(f).issubset(allowed):
        raise ValueError("Invalid update fields")

    with db() as c:
        c.execute(
            f"UPDATE orders SET {', '.join(k + '=%s' for k in f)} WHERE code=%s",
            (*f.values(), code),
        )


def claim(code, frm, to):
    """Atomic status change; prevents double purchases on parallel clicks."""
    with db() as c:
        return c.execute(
            "UPDATE orders SET status=%s WHERE code=%s AND status=%s",
            (to, code, frm),
        ).rowcount == 1


def new_code(tier, amount):
    offer = OFFERS.get(tier)
    if not offer or not offer["min"] <= amount <= offer["max"]:
        raise HTTPException(400, "Invalid package")

    # Retry on the extremely unlikely chance of a collision.
    for _ in range(5):
        code = secrets.token_hex(5)
        try:
            with db() as c:
                c.execute(
                    """
                    INSERT INTO orders(code,tier,amount,created_at)
                    VALUES(%s,%s,%s,%s)
                    """,
                    (code, tier, amount, int(time.time())),
                )
            return code
        except psycopg.errors.UniqueViolation:
            continue

    raise HTTPException(500, "Could not generate a unique code")


async def vc(path, payload):
    async with httpx.AsyncClient(timeout=50) as c:
        r = await c.post(
            "https://api.vaultcord.com" + path,
            json=payload,
            headers={"Authorization": f"Bearer {VC_KEY}"},
        )
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


# ---------- Pages ----------
FAQ = [
    ("How do I redeem a code?",
     "Enter your code, server invite link and email, add the bot to your server, then start the delivery."),
    ("Do I need an account?", "No. The code from your order is enough."),
    ("Which invite link should I use?",
     "One that never expires and has no use limit. Otherwise the delivery can fail."),
    ("How long does delivery take?",
     "It starts once the bot is on your server and you start the delivery. The duration depends on the amount."),
    ("Can members leave the server again?",
     "Yes, members can leave at any time. There is no guarantee on how long they stay."),
    ("What if something goes wrong?",
     "Contact support with your code and we will look at the order."),
]

CSS = """
:root{color-scheme:dark;--ink:#0f1218;--panel:#161a22;--line:#262c38;--text:#e9ecf2;--muted:#8b93a5;--accent:#7c9cff}
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--text);font:16px/1.55 Manrope,system-ui,sans-serif}
header{display:flex;justify-content:space-between;align-items:center;max-width:1040px;margin:0 auto;padding:20px}
.logo{font-weight:800;font-size:1.15rem;color:var(--text);text-decoration:none}
nav a{margin-left:22px;color:var(--muted);text-decoration:none}
nav a:hover{color:var(--text)}
a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.hero{max-width:1040px;margin:0 auto;padding:48px 20px 40px;display:grid;grid-template-columns:1.15fr .85fr;gap:56px;align-items:center}
.hero h1{font-size:clamp(2.2rem,5.2vw,3.7rem);line-height:1.05;letter-spacing:-.02em;font-weight:800;margin:0 0 18px}
.lead{font-size:1.1rem;color:var(--muted);max-width:34em;margin:0}
.feats{max-width:1040px;margin:0 auto;padding:36px 20px 72px;display:grid;grid-template-columns:repeat(3,1fr);gap:32px}
.feats div{border-top:2px solid var(--line);padding-top:16px}
.feats b{display:block;margin-bottom:4px}
.feats span{color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:26px}
.card h1,.card h2{font-size:1.3rem;margin:0 0 6px}
.narrow{max-width:460px;margin:0 auto;padding:28px 20px 64px}
.narrow h1{font-size:1.8rem}
label{display:block;margin:16px 0 6px;font-size:.9rem;color:var(--muted)}
input{width:100%;padding:12px;border-radius:8px;border:1px solid var(--line);background:var(--ink);color:inherit;font:inherit}
button,.btn{display:block;width:100%;margin-top:20px;padding:13px;border:0;border-radius:8px;background:var(--accent);color:var(--ink);font:inherit;font-weight:800;text-align:center;text-decoration:none;cursor:pointer}
.msg{padding:10px 12px;border-radius:8px;background:#3a2326;color:#ffb4b4}
.hint{color:var(--muted);font-size:.9rem;margin-bottom:0}
details{border-top:1px solid var(--line);padding:16px 0}
summary{cursor:pointer;font-weight:600}
details p{color:var(--muted);margin:10px 0 0}
@media(max-width:820px){.hero{grid-template-columns:1fr;gap:32px;padding-top:24px}.feats{grid-template-columns:1fr;gap:24px}}
"""

HERO = """
<h1>Members for your Discord server.</h1>
<p class="lead">Enter the code from your order, add the bot, start the delivery. Three steps, no account.</p>
"""

FEATS = """
<section class="feats">
<div><b>No account</b><span>One code per order, that is all you need.</span></div>
<div><b>You start it</b><span>Delivery begins once the bot is on your server.</span></div>
<div><b>Clear status</b><span>See at any time whether your order is running or done.</span></div>
</section>
"""


def shell(content):
    e = html.escape
    return HTMLResponse(f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(BRAND)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
<header><a class="logo" href="/">{e(BRAND)}</a><nav><a href="/">Redeem</a><a href="/faq">FAQ</a><a href="{e(SUPPORT_URL)}">Support</a></nav></header>
{content}</html>""")


def page(body):
    if "<!--landing-->" in body:
        return shell(f'<section class="hero"><div>{HERO}</div><div class="card">{body}</div></section>{FEATS}')
    return shell(f'<main class="narrow"><div class="card">{body}</div></main>')


def form(code="", msg=""):
    e = html.escape
    note = f'<p class="msg">{e(msg)}</p>' if msg else ""
    return f"""<!--landing--><h2>Redeem code</h2>{note}
<form method="post" action="/redeem">
<label for="code">Code</label><input id="code" name="code" value="{e(code)}" required autocomplete="off">
<label for="invite">Server invite link</label><input id="invite" name="invite" placeholder="https://discord.gg/abc123" required>
<label for="email">Email</label><input id="email" name="email" type="email" required>
<button>Redeem</button></form>
<p class="hint">Use an invite link that does not expire.</p>"""


def view(o, msg=""):
    e = html.escape
    note = f'<p class="msg">{e(msg)}</p>' if msg else ""
    st = o["status"]

    if st == "new":
        return form(o["code"], msg)

    if st == "bought":
        return f"""<h1>Step 2: Add the bot</h1>{note}
<p>{o['amount']} members are reserved. Add the bot to your server, then start the delivery.</p>
<a class="btn" href="{e(o['bot_url'] or '')}" target="_blank" rel="noopener">Add bot</a>
<form method="post" action="/pull"><input type="hidden" name="code" value="{e(o['code'])}">
<button>Start delivery</button></form>"""

    if st == "pulled":
        return f"<h1>Delivered</h1>{note}<p>{o['amount']} members were sent to your server.</p>"

    return f"<h1>In progress</h1>{note}<p>Your order is running. Reload this page in a minute.</p>"


@app.get("/", response_class=HTMLResponse)
def index():
    return page(form())


@app.get("/faq", response_class=HTMLResponse)
def faq():
    items = "".join(
        f"<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>"
        for q, a in FAQ
    )
    return shell(
        f'<main class="narrow" style="max-width:640px">'
        f'<h1>Frequently asked questions</h1>{items}</main>'
    )


@app.get("/o/{code}", response_class=HTMLResponse)
def order_page(code: str):
    o = get(code.lower())
    return page(view(o) if o else form("", "Code not found."))


@app.post("/redeem", response_class=HTMLResponse)
async def redeem(
    code: str = Form(...),
    invite: str = Form(...),
    email: str = Form(...)
):
    code, email = code.strip().lower(), email.strip()
    o = get(code)

    if not o:
        return page(form(code, "Code not found."))

    if o["status"] != "new":
        return page(view(o))

    m = INVITE_RE.match(invite.strip())
    if not m or not EMAIL_RE.match(email):
        return page(form(code, "The invite link or email is invalid."))

    if not claim(code, "new", "buying"):
        return page(view(get(code)))

    offer = OFFERS[o["tier"]]
    local, domain = email.split("@", 1)
    payload = {
        "marketId": offer["market_id"],
        "inviteLink": m.group(1),
        "userEmail": f"{local.split('+')[0]}+{code}@{domain}",
        "amount": o["amount"],
        "budget": math.ceil(
            o["amount"] * offer["cents_per_100"] / 100 * BUDGET_BUFFER
        ),
    }

    try:
        status, data = await vc("/market/buy", payload)
    except httpx.HTTPError as ex:
        update(code, status="new", error=str(ex))
        return page(form(code, "VaultCord is not reachable right now. Please try again shortly."))

    if status != 200 or not data.get("success"):
        update(code, status="new", error=json.dumps(data)[:500])
        print(f"[BUY FAILED] {code} http={status} {data}")
        return page(form(code, "The order failed. Contact support with your code."))

    d = data["data"]
    update(
        code,
        status="bought",
        email=email,
        invite_link=m.group(1),
        order_id=d["orderId"],
        bot_url=d["inviteUrl"],
        cost=d.get("cost"),
    )
    return page(view(get(code)))


@app.post("/pull", response_class=HTMLResponse)
async def pull(code: str = Form(...)):
    code = code.strip().lower()
    o = get(code)

    if not o:
        return page(form(code, "Code not found."))

    if o["status"] != "bought" or not claim(code, "bought", "pulling"):
        return page(view(get(code)))

    try:
        status, data = await vc("/market/pull", {"orderId": o["order_id"]})
    except httpx.HTTPError as ex:
        update(code, status="bought", error=str(ex))
        return page(view(get(code), "VaultCord is not reachable right now. Please try again shortly."))

    if status == 200 and data.get("success"):
        update(code, status="pulled")
    else:
        update(code, status="bought", error=json.dumps(data)[:500])
        print(f"[PULL FAILED] {code} http={status} {data}")
        return page(view(get(code), "Delivery is not possible yet. Is the bot on your server? Then try again."))

    return page(view(get(code)))


# ---------- Admin + SellAuth ----------
ADMIN_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Member Shop Admin</title>
<style>
:root{color-scheme:dark;--bg:#0f1218;--panel:#161a22;--line:#262c38;--text:#e9ecf2;--muted:#9aa3b5;--accent:#7c9cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,sans-serif;padding:24px}
main{max-width:680px;margin:35px auto}.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:24px}
h1{margin-top:0}label{display:block;margin:16px 0 6px;color:var(--muted)}input,select,button{width:100%;padding:12px;border-radius:8px;border:1px solid var(--line);font:inherit}
input,select{background:var(--bg);color:var(--text)}button{margin-top:18px;background:var(--accent);color:#10131a;font-weight:800;border:0;cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--bg);padding:14px;border-radius:8px;min-height:70px}.hint{color:var(--muted);font-size:.9rem}.error{color:#ffaaaa}
</style>
</head><body><main><section class="card">
<h1>Redeem-Key Generator</h1>
<p class="hint">Generate order codes. Keep the admin token private.</p>
<form id="generator">
<label for="token">Admin token</label><input id="token" type="password" autocomplete="current-password" required>
<label for="count">Number of keys (1–500)</label><input id="count" type="number" min="1" max="500" value="10" required>
<label for="tier">Package</label><select id="tier"><option value="standard">Standard</option><option value="valid">Valid</option></select>
<label for="amount">Members per key</label><input id="amount" type="number" min="1" max="4000" value="50" required>
<button type="submit">Generate keys</button></form>
<h2>Generated keys</h2><pre id="results">Your keys will appear here.</pre><button id="copy" type="button">Copy results</button><p id="message" class="hint" role="status"></p>
</section></main>
<script>
const form=document.getElementById('generator'), tier=document.getElementById('tier'), amount=document.getElementById('amount');
tier.addEventListener('change',()=>{if(tier.value==='valid'){amount.min='1000';if(Number(amount.value)<1000)amount.value='1000'}else{amount.min='1';if(Number(amount.value)<1)amount.value='50'}});
form.addEventListener('submit',async event=>{event.preventDefault();const results=document.getElementById('results'),message=document.getElementById('message');results.textContent='Generating…';message.textContent='';
try{const response=await fetch('/admin/generate',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('token').value},body:JSON.stringify({count:Number(document.getElementById('count').value),tier:tier.value,amount:Number(amount.value)})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Could not generate keys');results.textContent=data.codes.map(item=>item.code+' — '+item.link).join('\n');message.textContent='Created '+data.count+' key(s). Save them securely.'}
catch(error){results.textContent='';message.textContent=error.message;message.className='error'}});
document.getElementById('copy').addEventListener('click',async()=>{const message=document.getElementById('message');try{await navigator.clipboard.writeText(document.getElementById('results').textContent);message.textContent='Copied.';message.className='hint'}catch{message.textContent='Clipboard access failed. Select and copy the text manually.';message.className='error'}});
</script></body></html>"""


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return HTMLResponse(ADMIN_PAGE)


@app.post("/admin/generate")
async def admin_generate(request: Request, x_admin_token: str = Header("")):
    """Generate multiple redeem/order codes from the admin page."""
    check_admin(x_admin_token)

    try:
        body = await request.json()
        count = body.get("count")
        tier = body.get("tier")
        amount = body.get("amount")

        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 500:
            raise HTTPException(400, "Count must be an integer between 1 and 500")

        if isinstance(amount, bool) or not isinstance(amount, int):
            raise HTTPException(400, "Member amount must be an integer")

        offer = OFFERS.get(tier)
        if not offer or not offer["min"] <= amount <= offer["max"]:
            raise HTTPException(400, "Invalid package or member amount")

        codes = []
        for _ in range(count):
            code = new_code(tier, amount)
            codes.append({"code": code, "link": f"{BASE_URL}/o/{code}"})

        return {"count": len(codes), "codes": codes}

    except HTTPException:
        raise
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Invalid request body")


def check_admin(token):
    if not ADMIN_TOKEN or not hmac.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(401, "Unauthorized")


@app.post("/admin/create")
async def admin_create(request: Request, x_admin_token: str = Header("")):
    """Create a code by hand: {"tier": "standard", "amount": 500}"""
    check_admin(x_admin_token)
    b = await request.json()
    code = new_code(b["tier"], int(b["amount"]))
    return {"code": code, "link": f"{BASE_URL}/o/{code}"}


@app.get("/admin/orders")
def admin_orders(x_admin_token: str = Header("")):
    check_admin(x_admin_token)
    with db() as c:
        return c.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT 200"
        ).fetchall()


def parse_order(payload):
    """TODO: read (tier, amount) from SellAuth webhook once a sample payload is available."""
    raise HTTPException(501, "parse_order is not implemented yet")


@app.post("/webhook/sellauth")
async def sellauth(request: Request, x_signature: str = Header("")):
    raw = await request.body()
    expected = hmac.new(
        SELLAUTH_SECRET.encode(), raw, hashlib.sha256
    ).hexdigest()

    if not SELLAUTH_SECRET or not hmac.compare_digest(expected, x_signature):
        raise HTTPException(401)

    tier, amount = parse_order(json.loads(raw))
    code = new_code(tier, amount)
    return PlainTextResponse(f"{BASE_URL}/o/{code}")
