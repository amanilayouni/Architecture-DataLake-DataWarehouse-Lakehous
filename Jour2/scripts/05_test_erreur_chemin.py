# Test d'erreur controle : dossier GetFile inexistant -> bulletin d'erreur -> retablissement.
import json, ssl, time, urllib.request

BASE = "https://localhost:8443/nifi-api"
CTX = ssl._create_unverified_context()
TOKEN = open("/home/amani/nifi_token.txt").read().strip()
GID = "ef51ad5b-01a1-1000-2c29-24827ce087aa"
LOG = open("/home/amani/preuves_j2/uc04_erreur_test.txt", "w")

def api(m, p, b=None):
    req = urllib.request.Request(BASE + p, method=m)
    req.add_header("Authorization", "Bearer " + TOKEN)
    d = None
    if b is not None:
        req.add_header("Content-Type", "application/json"); d = json.dumps(b).encode()
    r = urllib.request.urlopen(req, data=d, context=CTX, timeout=30)
    raw = r.read().decode()
    return json.loads(raw) if raw else {}

def log(*a):
    m = " ".join(str(x) for x in a); print(m); LOG.write(m + "\n"); LOG.flush()

# 1. arreter GetFile, casser le chemin, redemarrer
st = api("GET", "/processors/{0}".format(GID))
v = st["revision"]["version"]
api("PUT", "/processors/{0}/run-status".format(GID), {"revision": {"version": v}, "state": "STOPPED"})
time.sleep(4)
st = api("GET", "/processors/{0}".format(GID))
v = st["revision"]["version"]
r = api("PUT", "/processors/{0}".format(GID), {
    "revision": {"version": v},
    "component": {"id": GID,
                  "config": {"properties": {"Input Directory": "/home/amani/data_nifi/input_inexistant"}}}})
log("chemin casse en :", r["component"]["config"]["properties"]["Input Directory"])

st = api("GET", "/processors/{0}".format(GID))
v = st["revision"]["version"]
r = api("PUT", "/processors/{0}/run-status".format(GID), {"revision": {"version": v}, "state": "RUNNING"})
log("GetFile relance avec chemin faux ->", r["component"]["state"])
time.sleep(40)

# 2. bulletins
bul = api("GET", "/flow/bulletin-board")
found = False
for b in bul.get("bulletinBoard", {}).get("bulletins", []):
    msg = b.get("bulletin", {}).get("message", "")
    if msg:
        found = True
        log("BULLETIN:", msg[:300])
if not found:
    log("pas de bulletin")
# verifier le log nifi cote fichier
log("(voir aussi nifi-app.log)")

# 3. retablir
st = api("GET", "/processors/{0}".format(GID))
v = st["revision"]["version"]
api("PUT", "/processors/{0}/run-status".format(GID), {"revision": {"version": v}, "state": "STOPPED"})
time.sleep(4)
st = api("GET", "/processors/{0}".format(GID))
v = st["revision"]["version"]
api("PUT", "/processors/{0}".format(GID), {
    "revision": {"version": v},
    "component": {"id": GID,
                  "config": {"properties": {"Input Directory": "/home/amani/data_nifi/input"}}}})
st = api("GET", "/processors/{0}".format(GID))
v = st["revision"]["version"]
r = api("PUT", "/processors/{0}/run-status".format(GID), {"revision": {"version": v}, "state": "RUNNING"})
log("chemin retabli, GetFile ->", r["component"]["state"])

LOG.close()
print("TERMINE")
