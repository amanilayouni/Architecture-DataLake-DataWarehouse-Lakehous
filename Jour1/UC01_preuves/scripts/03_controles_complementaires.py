"""UC-01 – Étape D (suite) : lever les ambiguïtés de relations détectées par 02_relations_controles.py.

Usage : python 03_controles_complementaires.py <racine_kit> <dossier_sortie>

  a. wcs_sales_sk / pr_order_sk : la plage de valeurs (0-89099) est commune à ss_ticket_number et
     ws_order_number. On teste donc des correspondances composites (numéro + produit, numéro + client).
  b. retours : date de retour >= date de vente, quantité retournée <= quantité vendue.
  c. inventory (data) : les produits orphelins sont-ils fournis par data_refresh/item ?
  d. divers : hd_vehicle_count négatif, magasins « fermés » avant leurs ventes, chevauchement data / refresh.
Sortie : 07_controles_complementaires.json
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from tpcxbb_schema import SCHEMA  # noqa: E402

ROOT, OUT = sys.argv[1], sys.argv[2]
IDX = {t: {c: i for i, c in enumerate(cols)} for t, cols in SCHEMA.items()}


def rows(kit, table):
    n = len(SCHEMA[table])
    with open(os.path.join(ROOT, kit, table, f"{table}.dat"), encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\r\n").split("|")
            if len(p) == n:
                yield p


DATE = {r[0]: r[2] for r in rows("data", "date_dim")}
R = {}

# ventes : (item, numero) -> [date_sk, qte, client]
SS, WS = defaultdict(list), defaultdict(list)
SS_CUST, WS_CUST = {}, {}
for r in rows("data", "store_sales"):
    SS[(r[2], r[9])].append((int(r[0]), int(r[10])))
    SS_CUST[r[9]] = r[3]
for r in rows("data", "web_sales"):
    WS[(r[3], r[17])].append((int(r[0]), int(r[18])))
    WS_CUST[r[17]] = r[4]

# a. clickstreams
c = Counter()
for r in rows("data", "web_clickstreams"):
    if not r[2]:
        continue
    c["clics_avec_wcs_sales_sk"] += 1
    c["(wcs_item_sk,wcs_sales_sk) dans web_sales (ws_item_sk,ws_order_number)"] += (r[3], r[2]) in WS
    c["(wcs_item_sk,wcs_sales_sk) dans store_sales (ss_item_sk,ss_ticket_number)"] += (r[3], r[2]) in SS
    if r[5]:
        c["clics_avec_sales_sk_et_user"] += 1
        c["wcs_user_sk = ws_bill_customer_sk de la commande"] += WS_CUST.get(r[2]) == r[5]
        c["wcs_user_sk = ss_customer_sk du ticket"] += SS_CUST.get(r[2]) == r[5]
R["web_clickstreams_vs_ventes"] = dict(c)

c = Counter()
for r in rows("data", "product_reviews"):
    c["avis"] += 1
    c["(pr_item_sk,pr_order_sk) dans web_sales"] += (r[4], r[6]) in WS
    c["(pr_item_sk,pr_order_sk) dans store_sales"] += (r[4], r[6]) in SS
    c["pr_user_sk = ws_bill_customer_sk de la commande"] += WS_CUST.get(r[6]) == r[5]
    c["pr_user_sk = ss_customer_sk du ticket"] += SS_CUST.get(r[6]) == r[5]
R["product_reviews_vs_ventes"] = dict(c)

# b. retours
for table, sales, di, ii, ni, qi in [("store_returns", SS, 0, 2, 9, 10), ("web_returns", WS, 0, 2, 13, 14)]:
    c = Counter()
    for r in rows("data", table):
        lines = sales.get((r[ii], r[ni]), [])
        c["retours"] += 1
        c["cle_vente_ambigue(plusieurs lignes de vente)"] += len(lines) > 1
        if lines:
            c["date_retour<date_vente"] += int(r[di]) < min(d for d, _ in lines)
            c["qte_retournee>qte_vendue"] += int(r[qi]) > sum(q for _, q in lines)
            delay = int(r[di]) - min(d for d, _ in lines)
            c["delai_retour_max_jours"] = max(c["delai_retour_max_jours"], delay)
            c["_somme_delais"] += delay
    c["delai_retour_moyen_jours"] = round(c.pop("_somme_delais") / c["retours"], 1)
    R[f"{table}_chronologie"] = dict(c)

# c. inventory orphelins vs refresh
ref_items = {r[0] for r in rows("data_refresh", "item")}
data_items = {r[0] for r in rows("data", "item")}
orph = Counter()
for r in rows("data", "inventory"):
    if r[1] not in data_items:
        orph["orphelins"] += 1
        orph["dont_couverts_par_data_refresh_item"] += r[1] in ref_items
R["inventory_orphelins_vs_refresh"] = dict(orph)

# d. divers
R["hd_vehicle_count_negatif"] = sum(1 for r in rows("data", "household_demographics") if r[4].startswith("-"))
first_sale = {}
for r in rows("data", "store_sales"):
    first_sale[r[7]] = min(first_sale.get(r[7], 10 ** 9), int(r[0]))
R["store_ferme_avant_premiere_vente"] = [
    {"s_store_sk": r[0], "s_store_name": r[5], "date_fermeture": DATE.get(r[4]),
     "premiere_vente": DATE.get(str(first_sale.get(r[0])))}
    for r in rows("data", "store") if r[4] and r[0] in first_sale and int(r[4]) < first_sale[r[0]]]
for t, col in [("store_sales", 0), ("web_sales", 0), ("web_clickstreams", 0)]:
    d = sorted({int(r[col]) for r in rows("data_refresh", t)})
    dd = sorted({int(r[col]) for r in rows("data", t)})
    R[f"periode_{t}"] = {"data": [DATE[str(dd[0])], DATE[str(dd[-1])]], "data_refresh": [DATE[str(d[0])], DATE[str(d[-1])]],
                         "jours_communs": [DATE[str(x)] for x in sorted(set(d) & set(dd))]}

# f. rattachement des faits du lot data_refresh aux ventes (data + data_refresh)
SSR = {(r[2], r[9]) for r in rows("data_refresh", "store_sales")}
WSR = {(r[3], r[17]) for r in rows("data_refresh", "web_sales")}
f = Counter()
for r in rows("data_refresh", "store_returns"):
    k = (r[2], r[9]); f["store_returns"] += 1
    f["store_returns_dans_data"] += k in SS; f["store_returns_dans_refresh"] += k in SSR
for r in rows("data_refresh", "web_returns"):
    k = (r[2], r[13]); f["web_returns"] += 1
    f["web_returns_dans_data"] += k in WS; f["web_returns_dans_refresh"] += k in WSR
for r in rows("data_refresh", "web_clickstreams"):
    if r[2]:
        f["clics_avec_vente"] += 1; f["clics_avec_vente_dans_ws_refresh"] += (r[3], r[2]) in WSR
for r in rows("data_refresh", "product_reviews"):
    k = (r[4], r[6]); f["avis"] += 1
    f["avis_dans_ws_data"] += k in WS; f["avis_dans_ws_refresh"] += k in WSR
R["data_refresh_rattachement_aux_ventes"] = dict(f)

# e. valeurs de test des KPI stock / avis (preuve de calculabilité)
snap = defaultdict(Counter)
for r in rows("data", "inventory"):
    s = snap[r[0]]
    s["lignes"] += 1
    if r[3] == "":
        s["qte_vide"] += 1
    else:
        s["qte_totale"] += int(r[3])
        s["qte_zero"] += r[3] == "0"
first, last = min(snap, key=int), max(snap, key=int)
R["kpi_stock"] = {f"releve_{DATE[k]}": dict(snap[k]) for k in (first, last)}
ratings = [int(r[3]) for r in rows("data", "product_reviews")]
R["kpi_avis"] = {"nb_avis": len(ratings), "note_moyenne": round(sum(ratings) / len(ratings), 3)}

with open(os.path.join(OUT, "07_controles_complementaires.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=1))
