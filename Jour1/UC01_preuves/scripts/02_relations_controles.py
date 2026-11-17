"""UC-01 – Étape D : vérification des relations possibles et contrôles simples.

Usage :
    python 02_relations_controles.py <racine_kit> <dossier_sortie>

Contrôles réalisés (lecture seule, en flux) :
  1. intégrité référentielle des clés étrangères candidates (orphelins, nulls) ;
  2. rattachement retours -> ventes (clé composite produit + ticket / commande) ;
  3. cardinalités : lignes par ticket / commande, unicité date-magasin-client par ticket ;
  4. cohérence arithmétique des montants (prix x quantité, remise, net payé, marge) ;
  5. couverture temporelle (dates min / max, lignes par année) ;
  6. KPI de test par année (CA, transactions, panier moyen, quantités, taux de remise, retours) ;
  7. navigation : part des clics rattachés à une vente, part des visiteurs anonymes ;
  8. data_refresh : recouvrement des clés avec le jeu initial ;
  9. anomalies de référentiels (date_dim, store, customer, promotion, item_marketprices).
Sortie : 06_relations_controles.json
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from tpcxbb_schema import SCHEMA  # noqa: E402

ROOT, OUT = sys.argv[1], sys.argv[2]
IDX = {t: {c: i for i, c in enumerate(cols)} for t, cols in SCHEMA.items()}
R = {}  # résultats


def rows(kit, table):
    p = os.path.join(ROOT, kit, table, f"{table}.dat")
    if not os.path.exists(p):
        return
    n = len(SCHEMA[table])
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as f:
        for line in f:
            parts = line.rstrip("\r\n").split("|")
            if len(parts) == n:
                yield parts


def keyset(kit, table, col):
    i = IDX[table][col]
    return {r[i] for r in rows(kit, table) if r[i] != ""}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------- référentiels
log("chargement des référentiels")
DIM = {}
for kit in ("data", "data_refresh"):
    for t, c in [("customer", "c_customer_sk"), ("customer_address", "ca_address_sk"), ("item", "i_item_sk"),
                 ("customer_demographics", "cd_demo_sk"), ("household_demographics", "hd_demo_sk"),
                 ("income_band", "ib_income_band_sk"), ("store", "s_store_sk"), ("promotion", "p_promo_sk"),
                 ("warehouse", "w_warehouse_sk"), ("web_page", "wp_web_page_sk"), ("web_site", "web_site_sk"),
                 ("ship_mode", "sm_ship_mode_sk"), ("reason", "r_reason_sk"), ("time_dim", "t_time_sk"),
                 ("date_dim", "d_date_sk")]:
        s = keyset(kit, t, c)
        if s:
            DIM[(kit, t)] = s
DATE = {}  # d_date_sk -> (date ISO, année)
for r in rows("data", "date_dim"):
    DATE[r[0]] = (r[2], int(r[6]))
ITEM_CAT = {r[0]: r[IDX["item"]["i_category"]] for r in rows("data", "item")}


def dim(table, refresh=False):
    s = set(DIM.get(("data", table), set()))
    if refresh:
        s |= DIM.get(("data_refresh", table), set())
    return s


# ---------------------------------------------------------------- 1. FK génériques
FKS = {
    "store_sales": [("ss_sold_date_sk", "date_dim"), ("ss_sold_time_sk", "time_dim"), ("ss_item_sk", "item"),
                    ("ss_customer_sk", "customer"), ("ss_cdemo_sk", "customer_demographics"),
                    ("ss_hdemo_sk", "household_demographics"), ("ss_addr_sk", "customer_address"),
                    ("ss_store_sk", "store"), ("ss_promo_sk", "promotion")],
    "store_returns": [("sr_returned_date_sk", "date_dim"), ("sr_return_time_sk", "time_dim"),
                      ("sr_item_sk", "item"), ("sr_customer_sk", "customer"), ("sr_store_sk", "store"),
                      ("sr_reason_sk", "reason")],
    "web_sales": [("ws_sold_date_sk", "date_dim"), ("ws_sold_time_sk", "time_dim"),
                  ("ws_ship_date_sk", "date_dim"), ("ws_item_sk", "item"), ("ws_bill_customer_sk", "customer"),
                  ("ws_ship_customer_sk", "customer"), ("ws_web_page_sk", "web_page"),
                  ("ws_web_site_sk", "web_site"), ("ws_ship_mode_sk", "ship_mode"),
                  ("ws_warehouse_sk", "warehouse"), ("ws_promo_sk", "promotion")],
    "web_returns": [("wr_returned_date_sk", "date_dim"), ("wr_item_sk", "item"),
                    ("wr_refunded_customer_sk", "customer"), ("wr_returning_customer_sk", "customer"),
                    ("wr_web_page_sk", "web_page"), ("wr_reason_sk", "reason")],
    "inventory": [("inv_date_sk", "date_dim"), ("inv_item_sk", "item"), ("inv_warehouse_sk", "warehouse")],
    "web_clickstreams": [("wcs_click_date_sk", "date_dim"), ("wcs_click_time_sk", "time_dim"),
                         ("wcs_item_sk", "item"), ("wcs_web_page_sk", "web_page"), ("wcs_user_sk", "customer")],
    "product_reviews": [("pr_item_sk", "item"), ("pr_user_sk", "customer")],
    "item_marketprices": [("imp_item_sk", "item"), ("imp_start_date", "date_dim"), ("imp_end_date", "date_dim")],
    "customer": [("c_current_cdemo_sk", "customer_demographics"), ("c_current_hdemo_sk", "household_demographics"),
                 ("c_current_addr_sk", "customer_address"), ("c_first_sales_date_sk", "date_dim"),
                 ("c_first_shipto_date_sk", "date_dim")],
    "household_demographics": [("hd_income_band_sk", "income_band")],
    "promotion": [("p_item_sk", "item"), ("p_start_date_sk", "date_dim"), ("p_end_date_sk", "date_dim")],
    "store": [("s_closed_date_sk", "date_dim")],
    "web_page": [("wp_creation_date_sk", "date_dim"), ("wp_access_date_sk", "date_dim"),
                 ("wp_customer_sk", "customer")],
}

# accumulateurs des contrôles spécifiques, alimentés pendant le même passage
fk = {}
SS_KEYS, WS_KEYS = set(), set()
ss_ticket = defaultdict(lambda: [0, None, set()])  # nb lignes, (date, store, customer) , ensemble de combinaisons
ws_order = defaultdict(lambda: [0, set()])
kpi = defaultdict(lambda: defaultdict(float))
txn = defaultdict(set)
arith = Counter()
cat_ca = Counter()
store_ca = Counter()
days = defaultdict(set)
TOL = 0.011


def fnum(x):
    return float(x) if x else 0.0


def scan(kit, table):
    refresh = kit == "data_refresh"
    I = IDX[table]
    checks = [(c, I[c], dim(t, refresh), t) for c, t in FKS.get(table, [])]
    acc = {c: [0, 0, 0, []] for c, _, _, _ in checks}  # total, null, orphelins, exemples
    n = 0
    for r in rows(kit, table):
        n += 1
        for c, i, s, _ in checks:
            v = r[i]
            a = acc[c]
            a[0] += 1
            if v == "":
                a[1] += 1
            elif v not in s:
                a[2] += 1
                if len(a[3]) < 5:
                    a[3].append(v)
        if kit == "data":
            specific(table, r)
        else:
            specific_refresh(table, r)
    for c, _, s, t in checks:
        tot, nul, orph, ex = acc[c]
        fk[f"{kit}.{table}.{c} -> {t}"] = {
            "lignes": tot, "nulls": nul, "pct_nulls": round(100 * nul / tot, 3) if tot else 0,
            "orphelins": orph, "pct_orphelins_sur_renseignes": round(100 * orph / (tot - nul), 4) if tot - nul else 0,
            "exemples_orphelins": ex, "taille_referentiel": len(s),
            "referentiel": "data + data_refresh" if refresh else "data"}
    return n


def year_of(dsk):
    d = DATE.get(dsk)
    return d[1] if d else None


def specific(table, r):
    I = IDX[table]
    if table == "store_sales":
        it, tk, dsk = r[I["ss_item_sk"]], r[I["ss_ticket_number"]], r[I["ss_sold_date_sk"]]
        SS_KEYS.add((it, tk))
        t = ss_ticket[tk]
        t[0] += 1
        t[2].add((dsk, r[I["ss_store_sk"]], r[I["ss_customer_sk"]]))
        y = year_of(dsk)
        q = fnum(r[I["ss_quantity"]]); sp = fnum(r[I["ss_sales_price"]]); lp = fnum(r[I["ss_list_price"]])
        ext = fnum(r[I["ss_ext_sales_price"]]); disc = fnum(r[I["ss_ext_discount_amt"]])
        extl = fnum(r[I["ss_ext_list_price"]]); np_ = fnum(r[I["ss_net_paid"]]); cp = fnum(r[I["ss_coupon_amt"]])
        tax = fnum(r[I["ss_ext_tax"]]); npt = fnum(r[I["ss_net_paid_inc_tax"]])
        wh = fnum(r[I["ss_ext_wholesale_cost"]]); pr = fnum(r[I["ss_net_profit"]])
        arith["ss_lignes"] += 1
        arith["ss_ext_sales!=prix*qte"] += abs(ext - sp * q) > TOL
        arith["ss_remise!=(liste-vente)*qte"] += abs(disc - (lp - sp) * q) > TOL
        arith["ss_net_paid!=ext_sales-coupon"] += abs(np_ - (ext - cp)) > TOL
        arith["ss_net_paid_inc_tax!=net_paid+tax"] += abs(npt - (np_ + tax)) > TOL
        arith["ss_profit!=net_paid-cout"] += abs(pr - (np_ - wh)) > TOL
        arith["ss_qte<=0"] += q <= 0
        arith["ss_prix_vente>prix_liste"] += sp > lp + TOL
        arith["ss_qte_nulle(vide)"] += r[I["ss_quantity"]] == ""
        arith["ss_profit<0"] += pr < 0
        k = kpi[("magasin", y)]
        k["lignes"] += 1; k["ca_ext_sales_price"] += ext; k["net_paid"] += np_; k["quantite"] += q
        k["remise"] += disc; k["montant_liste"] += extl; k["marge"] += pr
        txn[("magasin", y)].add(tk)
        cat_ca[ITEM_CAT.get(it, "?")] += ext
        store_ca[r[I["ss_store_sk"]]] += ext
        if dsk in DATE:
            days["store_sales"].add(DATE[dsk][0])
    elif table == "web_sales":
        it, on, dsk = r[I["ws_item_sk"]], r[I["ws_order_number"]], r[I["ws_sold_date_sk"]]
        WS_KEYS.add((it, on))
        o = ws_order[on]
        o[0] += 1
        o[1].add((dsk, r[I["ws_bill_customer_sk"]]))
        y = year_of(dsk)
        q = fnum(r[I["ws_quantity"]]); sp = fnum(r[I["ws_sales_price"]]); lp = fnum(r[I["ws_list_price"]])
        ext = fnum(r[I["ws_ext_sales_price"]]); disc = fnum(r[I["ws_ext_discount_amt"]])
        extl = fnum(r[I["ws_ext_list_price"]]); np_ = fnum(r[I["ws_net_paid"]]); cp = fnum(r[I["ws_coupon_amt"]])
        wh = fnum(r[I["ws_ext_wholesale_cost"]]); pr = fnum(r[I["ws_net_profit"]])
        arith["ws_lignes"] += 1
        arith["ws_ext_sales!=prix*qte"] += abs(ext - sp * q) > TOL
        arith["ws_remise!=(liste-vente)*qte"] += abs(disc - (lp - sp) * q) > TOL
        arith["ws_net_paid!=ext_sales-coupon"] += abs(np_ - (ext - cp)) > TOL
        arith["ws_profit!=net_paid-cout"] += abs(pr - (np_ - wh)) > TOL
        arith["ws_qte<=0"] += q <= 0
        arith["ws_ship_date<sold_date"] += (r[I["ws_ship_date_sk"]] != "" and dsk != ""
                                           and int(r[I["ws_ship_date_sk"]]) < int(dsk))
        k = kpi[("web", y)]
        k["lignes"] += 1; k["ca_ext_sales_price"] += ext; k["net_paid"] += np_; k["quantite"] += q
        k["remise"] += disc; k["montant_liste"] += extl; k["marge"] += pr
        txn[("web", y)].add(on)
        if dsk in DATE:
            days["web_sales"].add(DATE[dsk][0])
    elif table in ("store_returns", "web_returns"):
        p = "sr" if table == "store_returns" else "wr"
        it = r[I[f"{p}_item_sk"]]
        num = r[I["sr_ticket_number" if p == "sr" else "wr_order_number"]]
        keys = SS_KEYS if p == "sr" else WS_KEYS
        arith[f"{p}_lignes"] += 1
        arith[f"{p}_rattaches_a_une_vente"] += (it, num) in keys
        y = year_of(r[I["sr_returned_date_sk" if p == "sr" else "wr_returned_date_sk"]])
        k = kpi[("retours_" + ("magasin" if p == "sr" else "web"), y)]
        k["lignes"] += 1
        k["quantite"] += fnum(r[I[f"{p}_return_quantity"]])
        k["montant_retour"] += fnum(r[I[f"{p}_return_amt"]])
        k["perte_nette"] += fnum(r[I[f"{p}_net_loss"]])
    elif table == "inventory":
        dsk = r[0]
        if dsk in DATE:
            days["inventory"].add(DATE[dsk][0])
        q = r[3]
        arith["inv_lignes"] += 1
        arith["inv_qte_vide"] += q == ""
        arith["inv_qte<0"] += q != "" and int(q) < 0
        arith["inv_qte=0"] += q == "0"
    elif table == "web_clickstreams":
        arith["wcs_lignes"] += 1
        arith["wcs_avec_sales_sk"] += r[2] != ""
        arith["wcs_user_vide"] += r[5] == ""
        arith["wcs_item_vide"] += r[3] == ""
        arith["wcs_avec_sales_sk_et_user_vide"] += r[2] != "" and r[5] == ""
        if r[2]:
            CLICK_SALES.add(r[2])
        if r[0] in DATE:
            days["web_clickstreams"].add(DATE[r[0]][0])
    elif table == "product_reviews":
        arith["pr_lignes"] += 1
        RATING[r[3]] += 1
        arith["pr_contenu_avec_entite_html"] += "&quot;" in r[7] or "&amp;" in r[7]
        if r[6]:
            REVIEW_ORDERS.add(r[6])
        d = r[1]
        if d:
            REVIEW_MINMAX[0] = min(REVIEW_MINMAX[0], d)
            REVIEW_MINMAX[1] = max(REVIEW_MINMAX[1], d)


CLICK_SALES, REVIEW_ORDERS = set(), set()
RATING = Counter()
REVIEW_MINMAX = ["9999", "0000"]
REFRESH = defaultdict(Counter)


def specific_refresh(table, r):
    I = IDX[table]
    c = REFRESH[table]
    c["lignes"] += 1
    if table == "store_sales":
        c["cle_(item,ticket)_deja_dans_data"] += (r[I["ss_item_sk"]], r[I["ss_ticket_number"]]) in SS_KEYS
        d = DATE.get(r[0]); c[f"annee_{d[1] if d else 'inconnue'}"] += 1
    elif table == "web_sales":
        c["cle_(item,order)_deja_dans_data"] += (r[I["ws_item_sk"]], r[I["ws_order_number"]]) in WS_KEYS
        d = DATE.get(r[0]); c[f"annee_{d[1] if d else 'inconnue'}"] += 1
    elif table in ("customer", "item", "customer_address"):
        k = r[0]
        c["cle_deja_dans_data"] += k in DIM.get(("data", table), set())
    elif table == "inventory":
        d = DATE.get(r[0]); c[f"date_{d[0] if d else 'inconnue'}"] += 1


t0 = time.time()
counts = {}
for kit in ("data", "data_refresh"):
    for table in ["store_sales", "web_sales", "store_returns", "web_returns", "inventory", "web_clickstreams",
                  "product_reviews", "item_marketprices", "customer", "household_demographics", "promotion",
                  "store", "web_page", "item", "customer_address"]:
        if os.path.exists(os.path.join(ROOT, kit, table, f"{table}.dat")):
            log(f"scan {kit}/{table}")
            counts[f"{kit}.{table}"] = scan(kit, table)
R["nb_lignes_scannees"] = counts
R["integrite_referentielle"] = fk

# ---------------------------------------------------------------- 2/3. retours, cardinalités
mono = sum(1 for t in ss_ticket.values() if len(t[2]) == 1)
lines_per_ticket = Counter(min(t[0], 30) for t in ss_ticket.values())
R["cardinalites"] = {
    "store_sales_tickets_distincts": len(ss_ticket),
    "store_sales_lignes_par_ticket_moy": round(sum(t[0] for t in ss_ticket.values()) / len(ss_ticket), 2),
    "store_sales_lignes_par_ticket_max": max(t[0] for t in ss_ticket.values()),
    "store_sales_tickets_avec_date_magasin_client_uniques": mono,
    "store_sales_tickets_incoherents(plusieurs date/magasin/client)": len(ss_ticket) - mono,
    "store_sales_cle_(item,ticket)_distinctes": len(SS_KEYS),
    "web_sales_commandes_distinctes": len(ws_order),
    "web_sales_lignes_par_commande_moy": round(sum(o[0] for o in ws_order.values()) / len(ws_order), 2),
    "web_sales_lignes_par_commande_max": max(o[0] for o in ws_order.values()),
    "web_sales_commandes_avec_date_client_uniques": sum(1 for o in ws_order.values() if len(o[1]) == 1),
    "web_sales_cle_(item,order)_distinctes": len(WS_KEYS),
    "web_clickstreams_wcs_sales_sk_distincts": len(CLICK_SALES),
    "web_clickstreams_wcs_sales_sk_presents_dans_ws_order_number": len(CLICK_SALES & set(ws_order)),
    "web_clickstreams_wcs_sales_sk_presents_dans_ss_ticket_number": len(CLICK_SALES & set(ss_ticket)),
    "product_reviews_pr_order_sk_distincts": len(REVIEW_ORDERS),
    "product_reviews_pr_order_sk_presents_dans_ws_order_number": len(REVIEW_ORDERS & set(ws_order)),
    "product_reviews_pr_order_sk_presents_dans_ss_ticket_number": len(REVIEW_ORDERS & set(ss_ticket)),
}
R["controles_arithmetiques_et_qualite"] = dict(arith)
R["product_reviews_notes"] = dict(sorted(RATING.items()))
R["product_reviews_periode"] = REVIEW_MINMAX

# ---------------------------------------------------------------- 5. couverture temporelle
cov = {}
for k, s in days.items():
    ds = sorted(s)
    per_year = Counter(d[:4] for d in ds)
    cov[k] = {"date_min": ds[0], "date_max": ds[-1], "nb_jours_distincts": len(ds),
              "jours_par_annee": dict(sorted(per_year.items()))}
    if k == "inventory":
        gaps = Counter((date.fromisoformat(b) - date.fromisoformat(a)).days for a, b in zip(ds, ds[1:]))
        cov[k]["ecart_entre_releves_jours"] = dict(gaps)
R["couverture_temporelle"] = cov

# ---------------------------------------------------------------- 6. KPI de test
out = {}
for (canal, y), k in sorted(kpi.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
    d = {m: round(v, 2) for m, v in k.items()}
    if canal in ("magasin", "web"):
        n_tx = len(txn[(canal, y)])
        d["transactions_distinctes"] = n_tx
        d["panier_moyen_ext_sales"] = round(k["ca_ext_sales_price"] / n_tx, 2) if n_tx else None
        d["taux_remise_pct"] = round(100 * k["remise"] / k["montant_liste"], 2) if k["montant_liste"] else None
    out[f"{canal}_{y}"] = d
R["kpi_de_test_par_annee"] = out
R["top10_categories_ca_magasin"] = [(c, round(v, 2)) for c, v in cat_ca.most_common(10)]
R["ca_magasin_par_store_sk"] = {k: round(v, 2) for k, v in sorted(store_ca.items(), key=lambda x: -x[1])}
R["data_refresh"] = {t: dict(c) for t, c in REFRESH.items()}

# ---------------------------------------------------------------- 9. anomalies de référentiels
anom = {}
dd = list(rows("data", "date_dim"))
anom["date_dim_lignes"] = len(dd)
anom["date_dim_periode"] = [dd[0][2], dd[-1][2]] if dd else None
day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
anom["date_dim_d_day_name_incoherent_avec_d_date"] = sum(
    1 for r in dd if day_names[date.fromisoformat(r[2]).weekday()] != r[14])
anom["date_dim_d_first_dom_hors_plage_d_date_sk"] = sum(1 for r in dd if r[19] not in DATE)
anom["date_dim_d_holiday_Y"] = sum(1 for r in dd if r[16] == "Y")
anom["date_dim_sk_contigus"] = all(int(r[0]) == i for i, r in enumerate(dd))
anom["date_dim_d_current_*_Y"] = sum(1 for r in dd if "Y" in r[23:28])
st = list(rows("data", "store"))
anom["store_nb"] = len(st)
anom["store_closed_dates"] = sorted({DATE.get(r[4], ("hors date_dim",))[0] for r in st if r[4]})
anom["store_etats"] = dict(Counter(r[IDX["store"]["s_state"]] for r in st))
anom["store_s_store_id_distincts"] = len({r[1] for r in st})
cu = list(rows("data", "customer"))
anom["customer_c_last_review_date_format_date"] = sum(1 for r in cu if len(r[17]) == 10 and r[17][4] == "-")
anom["customer_c_last_review_date_vide"] = sum(1 for r in cu if r[17] == "")
anom["customer_birth_year_min_max"] = [min(int(r[13]) for r in cu if r[13]), max(int(r[13]) for r in cu if r[13])]
anom["customer_c_customer_id_distincts"] = len({r[1] for r in cu})
anom["customer_pays_naissance_top5"] = Counter(r[14] for r in cu).most_common(5)
it = list(rows("data", "item"))
anom["item_nb"] = len(it)
anom["item_i_item_id_distincts"] = len({r[1] for r in it})
anom["item_categories"] = dict(Counter(r[12] for r in it).most_common())
anom["item_i_rec_end_date_renseigne"] = sum(1 for r in it if r[3])
anom["item_prix_vente<cout_achat"] = sum(1 for r in it if r[5] and r[6] and float(r[5]) < float(r[6]))
pm = list(rows("data", "promotion"))
anom["promotion_debut>fin"] = sum(1 for r in pm if r[2] and r[3] and int(r[2]) > int(r[3]))
imp = list(rows("data", "item_marketprices"))
anom["item_marketprices_debut>fin"] = sum(1 for r in imp if r[4] and r[5] and int(r[4]) > int(r[5]))
anom["item_marketprices_items_distincts"] = len({r[1] for r in imp})
anom["item_marketprices_concurrents_distincts"] = len({r[2] for r in imp})
sm = list(rows("data", "ship_mode"))
anom["ship_mode_exemples_sm_type"] = [r[2] for r in sm[:5]]
wh = list(rows("data", "warehouse"))
anom["warehouse_nb"] = len(wh)
R["anomalies_referentiels"] = anom
R["duree_s"] = round(time.time() - t0, 1)

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "06_relations_controles.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
log(f"terminé en {R['duree_s']} s")
