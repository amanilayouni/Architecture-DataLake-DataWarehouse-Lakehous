# Ajoute LogAttribute sur la relation failure de PutHDFS, demarre PutHDFS,
# releve les compteurs, la destination HDFS et la provenance.
import json, ssl, time, urllib.request

BASE = "https://localhost:8443/nifi-api"
CTX = ssl._create_unverified_context()
TOKEN = open("/home/amani/nifi_token.txt").read().strip()
GID = "ef51ad5b-01a1-1000-2c29-24827ce087aa"
PID = "ef65d6ad-01a1-1000-84db-5e02d586a5ec"
CID = "ef65ff28-01a1-1000-9779-80eea83952db"
PG = "ef49f569-01a1-1000-5059-6996b38ff816"
LOG = open("/home/amani/preuves_j2/uc04_api_log.txt", "a")

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

# --- LogAttribute pour la relation failure ---
lg = api("POST", "/process-groups/{0}/processors".format(PG), {
    "revision": {"version": 0},
    "component": {"type": "org.apache.nifi.processors.standard.LogAttribute",
                  "name": "LogAttribute_echecs",
                  "position": {"x": 700, "y": 450}}})
lid = lg["id"]; lv = lg["revision"]["version"]
log("LogAttribute cree:", lid)

# auto-terminer success de LogAttribute
r = api("PUT", "/processors/{0}".format(lid), {
    "revision": {"version": lv},
    "component": {"id": lid,
                  "config": {"autoTerminatedRelationships": ["success"]}}})
log("LogAttribute validation:", r.get("component", {}).get("validationStatus"))

# connexion PutHDFS.failure -> LogAttribute
conn2 = api("POST", "/process-groups/{0}/connections".format(PG), {
    "revision": {"version": 0},
    "component": {
        "source": {"id": PID, "groupId": PG, "type": "PROCESSOR"},
        "destination": {"id": lid, "groupId": PG, "type": "PROCESSOR"},
        "selectedRelationships": ["failure"]}})
cid2 = conn2["id"]
log("connexion failure -> LogAttribute:", cid2)

# verifier et demarrer PutHDFS puis LogAttribute
for name, i in [("PutHDFS", PID), ("LogAttribute", lid)]:
    st = api("GET", "/processors/{0}".format(i))
    comp = st["component"]
    log(name, "validation:", comp["validationStatus"],
        "| erreurs:", comp.get("validationErrors"))
    v = st["revision"]["version"]
    r = api("PUT", "/processors/{0}/run-status".format(i),
            {"revision": {"version": v}, "state": "RUNNING"})
    log(name, "->", r["component"]["state"])

time.sleep(25)

# compteurs via le statut du process group racine
f = api("GET", "/flow/process-groups/{0}".format(PG))
snap = f["processGroupFlow"]["flow"]
for p in snap["processors"]:
    s = p["status"]["aggregateSnapshot"]
    log("PROC", p["component"]["name"], "| state:", p["component"]["state"],
        "| in:", s["input"], "| out:", s["output"], "| tasks:", s["taskCount"])
for co in snap["connections"]:
    s = co["status"]["aggregateSnapshot"]
    log("CONN | queued:", s["queued"], "| in:", s["input"], "| out:", s["output"])

# bulletins (erreurs visibles)
try:
    bul = api("GET", "/flow/bulletin-board")
    for b in bul.get("bulletinBoard", {}).get("bulletins", []):
        log("BULLETIN:", b.get("bulletin", {}).get("message", "")[:200])
except Exception as e:
    log("bulletins: pas d'acces", e)

# provenance
prov = api("POST", "/provenance", {"provenance": {"request": {"maxResults": 25}}})
qid = prov["provenance"]["id"]
for _ in range(10):
    p = api("GET", "/provenance/{0}".format(qid))
    if p["provenance"]["finished"]:
        break
    time.sleep(3)
evs = p["provenance"]["results"]["provenanceEvents"]
with open("/home/amani/preuves_j2/uc04_provenance_events.json", "w") as fo:
    json.dump(evs, fo, indent=2)
log("evenements provenance:", len(evs))
for e in evs:
    log(" ", e.get("eventType"), "|", e.get("eventTime"), "|", e.get("fileName"),
        "|", (e.get("details") or "")[:90])

log("ids:", json.dumps({"getfile": GID, "puthdfs": PID, "logattr": lid,
                        "conn_success": CID, "conn_failure": cid2, "pg": PG}))
LOG.close()
print("TERMINE")
