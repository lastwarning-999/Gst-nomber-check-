import os
import re
import random
import string
import uuid
import json
import requests
from flask import Flask, render_template, request, flash, redirect, url_for
from fake_useragent import UserAgent

# Configure Flask to look for templates in the root directory
app = Flask(__name__, template_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# ------------------------------------------------------------
# Helper functions (copied and adapted from your script)
# ------------------------------------------------------------
def generate_fake_cookies():
    """Generate fake cookies (for development only)."""
    def rand_str(length, chars=string.ascii_letters + string.digits + "-_./"):
        return ''.join(random.choices(chars, k=length))

    cookies = {
        "__Secure-3PAPISID": rand_str(27) + "/" + rand_str(27),
        "__Secure-3PSID": "g.a0007gj" + rand_str(43),
        "NID": "529=" + rand_str(150, chars=string.ascii_letters + string.digits + "_-"),
        "__Secure-3PSIDCC": "AKEyXzX" + rand_str(50),
        "_ga_4TX14F3R0D": "GS2.1.s" + ''.join(random.choices(string.digits, k=10)) + "$o1$g0$t" + ''.join(random.choices(string.digits, k=10)) + "$j60$l0$h0",
        "_ga": "GA1.1." + ''.join(random.choices(string.digits, k=8)) + "." + ''.join(random.choices(string.digits, k=10)),
        "_ga_C37VX8T52R": "GS2.1.s" + ''.join(random.choices(string.digits, k=10)) + "$o1$g0$t" + ''.join(random.choices(string.digits, k=10)) + "$j58$l0$h0",
        "_gcl_au": "1.1." + ''.join(random.choices(string.digits, k=10)) + "." + ''.join(random.choices(string.digits, k=10)),
        "aI": str(uuid.uuid4()),
        "_uetsid": ''.join(random.choices(string.hexdigits.lower(), k=32)),
        "_uetvid": ''.join(random.choices(string.hexdigits.lower(), k=32)),
    }
    return cookies

def fake_ip_225():
    return f"225.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

ua = UserAgent()
def random_user_agent():
    return ua.random

def random_cb(length=12):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_recaptcha_token(session, site_key, referer, cb=None):
    if cb is None:
        cb = random_cb()
    anchor_url = "https://www.google.com/recaptcha/api2/anchor"
    params = {
        "ar": "1",
        "k": site_key,
        "co": "aHR0cHM6Ly9jbGVhcnRheC5pbjo0NDM.",
        "hl": "en",
        "type": "image",
        "v": "QvLuXwupqtKCyjBw2xIzFLIf",
        "theme": "light",
        "size": "invisible",
        "badge": "bottomright",
        "anchor-ms": "20000",
        "execute-ms": "30000",
        "cb": cb
    }
    headers = {
        "Host": "www.google.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
        "Referer": referer,
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "iframe",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": fake_ip_225(),
    }
    response = session.get(anchor_url, params=params, headers=headers)
    response.raise_for_status()
    match = re.search(r'<input[^>]*id="recaptcha-token"[^>]*value="([^"]+)"', response.text)
    if not match:
        raise RuntimeError("Could not find recaptcha token in the page")
    return match.group(1)

def get_gst_compliance_report(session, gstin, token):
    url = f"https://cleartax.in/f/compliance-report/{gstin}/"
    params = {"captcha_token": token}
    headers = {
        "Host": "cleartax.in",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
        "Referer": "https://cleartax.in/gst-number-search/",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Origin": "https://cleartax.in",
        "X-Forwarded-For": fake_ip_225(),
        "sentry-trace": ''.join(random.choices(string.hexdigits.lower(), k=32)) + '-' + ''.join(random.choices(string.hexdigits.lower(), k=16)) + '-1',
        "baggage": "sentry-environment=production,sentry-release=FakeRelease,sentry-public_key=fakepublickey,sentry-trace_id=" + ''.join(random.choices(string.hexdigits.lower(), k=32)) + ",sentry-sample_rate=1,sentry-transaction=fake,sentry-sampled=true",
    }
    response = session.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def extract_pan_from_gstin(gstin):
    if gstin and len(gstin) == 15:
        return gstin[2:12]
    return "N/A"

# ------------------------------------------------------------
# Flask Routes
# ------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        gstin = request.form.get('gstin', '').strip().upper()
        if len(gstin) != 15:
            flash('Invalid GSTIN. Must be 15 characters.', 'error')
            return redirect(url_for('index'))
        return redirect(url_for('result', gstin=gstin))
    return render_template('index.html')

@app.route('/result')
def result():
    gstin = request.args.get('gstin', '').strip().upper()
    if not gstin or len(gstin) != 15:
        flash('Invalid GSTIN.', 'error')
        return redirect(url_for('index'))

    # Get cookies from environment variable (JSON string) or fallback to fake
    cookies_json = os.environ.get('GOOGLE_COOKIES_JSON', '{}')
    try:
        cookies = json.loads(cookies_json)
    except:
        cookies = {}
    if not cookies:
        cookies = generate_fake_cookies()
        app.logger.warning("Using fake cookies – real cookies required for production.")

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
    })

    SITE_KEY = "6LevgAErAAAAAKzR-MPcdXwti7lpxV3-jOPM0vL2"
    REFERER = "https://cleartax.in/"

    try:
        token = get_recaptcha_token(session, SITE_KEY, REFERER)
        data = get_gst_compliance_report(session, gstin, token)
        taxpayer = data.get('taxpayerInfo', {})
        pan = extract_pan_from_gstin(gstin)
        return render_template('result.html', data=data, taxpayer=taxpayer, pan=pan, gstin=gstin)
    except requests.exceptions.HTTPError as e:
        flash(f"HTTP error: {e}. Check your cookies.", 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error fetching data: {str(e)}", 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
