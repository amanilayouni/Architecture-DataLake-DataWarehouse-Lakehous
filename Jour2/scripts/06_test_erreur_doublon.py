# Erreur controlee n2 : meme nom de fichier deja present dans HDFS.
# PutHDFS Conflict Resolution = fail -> FlowFile route en failure -> LogAttribute.
import json, os, shutil, ssl, time, urllib.request

BASE = "https://localhost:8443/nifi-api"
CTX = ssl._create_unverified_context()
TOKEN = open("/home/amani/nifi_token.txt").read().strip()
LID = "ef66dcf8-01a1-1000-cad7-c73ce99dbc21"
CID2 = "ef66dffc-01a1-1000-0392-57d2aa07ad7d"
PG = "ef49f569-01a1-1000-5059-6996b38ff816"
LOG = open("/home/amani/preuves_j2/uc04_erreur2_test.txt", "w")

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

# 1. reposer le meme fichier dans input (le precedent a ete consomme)
shutil.copy("/home/amani/retail_project/data/store/store.dat",
            "/home/amani/data_nifi/input/store.dat")
log("meme fichier repose dans input (le nom existe deja dans HDFS)")

# 2. attendre le traitement (GetFile 30s + PutHDFS 10s + marge)
time.sleep(70)

f = api("GET", "/flow/process-groups/{0}".format(PG))
snap = f["processGroupFlow"]["flow"]
for p in snap["processors"]:
    s = p["status"]["aggregateSnapshot"]
    log("PROC", p["component"]["name"], "| in:", s["input"], "| out:", s["output"],
        "| tasks:", s["taskCount"])
for co in snap["connections"]:
    s = co["status"]["aggregateSnapshot"]
    log("CONN", co.get("selectedRelationships", co.get("component", {}).get("selectedRelationships")),
        "| queued:", s["queued"], "| in:", s["input"], "| out:", s["output"])

# bulletins
bul = api("GET", "/flow/bulletin-board")
for b in bul.get("bulletinBoard", {}).get("bulletins", []):
    msg = b.get("bulletin", {}).get("message", "")
    if msg:
        log("BULLETIN:", msg[:300])

# provenance filtree sur les derniers evenements
prov = api("POST", "/provenance", {"provenance": {"request": {"maxResults": 15}}})
qid = prov["provenance"]["id"]
for _ in range(10):
    p = api("GET", "/provenance/{0}".format(qid))
    if p["provenance"]["finished"]:
        break
    time.sleep(3)
evs = p["provenance"]["results"]["provenanceEvents"]
with open("/home/amani/preuves_j2/uc04_provenance_events2.json", "w") as fo:
    json.dump(evs, fo, indent=2)
log("evenements:", len(evs))
for e in evs:
    log(" ", e.get("eventType"), "|", e.get("eventTime"), "|",
        (e.get("details") or "")[:120])
LOG.close()
print("TERMINE")
