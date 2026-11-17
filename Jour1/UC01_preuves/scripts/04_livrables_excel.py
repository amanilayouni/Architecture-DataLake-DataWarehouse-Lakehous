"""Génère 02_inventaire_sources.xlsx et 08_dictionnaire_KPI.xlsx à partir des preuves JSON.

Usage : python 04_livrables_excel.py      (après 01, 02 et 03)
"""
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRE = BASE  # dossier UC01_preuves
prof = json.load(open(os.path.join(PRE, "05_profil_fichiers.json"), encoding="utf-8"))
rel = json.load(open(os.path.join(PRE, "06_relations_controles.json"), encoding="utf-8"))
comp = json.load(open(os.path.join(PRE, "07_controles_complementaires.json"), encoding="utf-8"))

HEAD = PatternFill("solid", fgColor="D9D9D9")
WRAP = Alignment(wrap_text=True, vertical="top")


def sheet(wb, title, header, rows, widths=None):
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.font, c.fill, c.alignment = Font(bold=True), HEAD, WRAP
    for r in rows:
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
    for i, h in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(h, max(12, min(45, len(h) + 4)))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


# ------------------------------------------------------------------ notes par table (analyse)
NOTES = {
    "store_sales": ("1 ligne = 1 article sur un ticket de caisse", "CA, transactions, panier, quantités, remise, marge par magasin / produit / date",
                    "Silver ventes_magasin -> Gold fait_ventes (canal=magasin)",
                    "Montants cohérents (0 écart arithmétique). 4 038 couples (ss_item_sk, ss_ticket_number) apparaissent plusieurs fois : pas de clé naturelle unique au grain ligne. 74 % des lignes à marge négative (synthétique)."),
    "web_sales": ("1 ligne = 1 article d'une commande web", "CA web, commandes, panier, livraison, part du web",
                  "Silver ventes_web -> Gold fait_ventes (canal=web)",
                  "Montants cohérents. 4 076 couples (ws_item_sk, ws_order_number) dupliqués. Pas de colonne ws_sk (contrairement au document de référence)."),
    "store_returns": ("1 ligne = 1 article retourné d'un ticket", "Montants / quantités retournés, motifs, taux de retour",
                      "Silver retours_magasin -> Gold fait_retours", "100 % rattachés à une vente (produit + ticket) ; 470 rattachements ambigus (clé de vente dupliquée). Délai moyen 357 j (max 715 j) : peu réaliste."),
    "web_returns": ("1 ligne = 1 article retourné d'une commande", "Retours web, motifs, taux de retour",
                    "Silver retours_web -> Gold fait_retours", "100 % rattachés (produit + commande) ; 439 ambigus. Délai moyen 420 j (max 835 j)."),
    "inventory": ("1 ligne = stock d'un produit dans un entrepôt à une date (relevé hebdomadaire)", "Niveau de stock, ruptures",
                  "Silver stock -> Gold fait_stock_hebdo (mesure semi-additive)",
                  "Relevé tous les 7 jours (259 dates). 232 380 lignes référencent des produits 17820-17999 absents de data/item mais présents dans data_refresh/item. 5 999 quantités vides."),
    "web_clickstreams": ("1 ligne = 1 clic (date, heure, produit, page, utilisateur)", "Parcours visiteurs, clics liés à un achat",
                         "Silver navigation (partitionné par date) -> Gold agrégats navigation",
                         "Pas d'identifiant de clic ni de session (wcs_click_sk absent). 42 % de clics anonymes, 90 % sans vente. Clic avec vente = (produit, commande) web."),
    "product_reviews": ("1 ligne = 1 avis client sur un produit", "Note moyenne, verbatims (analyse de texte)",
                        "Bronze (texte brut) -> Silver avis -> Gold note par produit",
                        "Texte libre (non structuré dans un champ). 13 211 avis contiennent des entités HTML (&quot;). Rattachés aux commandes web."),
    "item_marketprices": ("1 ligne = prix d'un concurrent pour un produit sur une période", "Comparaison tarifaire",
                          "Silver prix_concurrents -> Gold écart de prix", "1 000 concurrents codés, aucune signification métier. 30 dates de fin vides."),
    "date_dim": ("1 ligne = 1 jour", "Axe temps (jour, mois, trimestre, année)", "Silver -> Gold dim_date",
                 "109 573 jours (1900-2199) au lieu de 73 049 selon la spec. d_holiday = 'Y' pour tous les jours. d_first_dom / d_last_dom / d_same_day_* codés en jour julien et non en d_date_sk."),
    "time_dim": ("1 ligne = 1 seconde de la journée", "Analyse horaire", "Silver -> Gold dim_heure", "t_meal_time vide à 58 % (normal hors repas)."),
    "customer": ("1 ligne = 1 client", "Référentiel client, segmentation", "Silver (pseudonymisé) -> Gold dim_client",
                 "Données personnelles synthétiques (nom, e-mail, date de naissance). 913 pays de naissance corrompus (caractère U+FFFD : R?UNION, C?TE D'IVOIRE). c_last_review_date contient des chaînes aléatoires."),
    "customer_address": ("1 ligne = 1 adresse", "Géographie client (état, ville)", "Silver -> Gold dim_client / dim_geo", "Pays unique : United States. Numéros de suite aléatoires."),
    "customer_demographics": ("1 ligne = 1 combinaison démographique", "Segmentation (genre, statut, éducation)", "Silver -> Gold dim_demographie", "Table combinatoire (1 920 800 lignes), ~0,025 % de nulls par attribut."),
    "household_demographics": ("1 ligne = 1 profil de foyer", "Segmentation foyer", "Silver -> Gold dim_foyer", "282 valeurs hd_vehicle_count = -1."),
    "income_band": ("1 ligne = 1 tranche de revenu", "Segmentation revenu", "Silver -> Gold dim_foyer", "Absente du document de référence, présente dans le kit."),
    "item": ("1 ligne = 1 produit", "Catalogue, catégories", "Silver -> Gold dim_produit",
             "Marques, fabricants et noms de produits aléatoires ; seules catégories / classes lisibles. 7 768 produits avec prix courant < coût d'achat. i_rec_end_date toujours vide."),
    "store": ("1 ligne = 1 magasin", "Référentiel magasin", "Silver -> Gold dim_magasin",
              "12 magasins. s_closed_date_sk renseigné pour tous (1917 -> 2141) : 5 magasins « fermés » avant leurs premières ventes. Surface (s_floor_space) peu plausible."),
    "warehouse": ("1 ligne = 1 entrepôt", "Référentiel entrepôt", "Silver -> Gold dim_entrepot", "5 entrepôts, noms aléatoires."),
    "promotion": ("1 ligne = 1 campagne", "Campagnes promotionnelles", "Silver -> Gold dim_promotion", "Noms de promotion tronqués / aléatoires, p_purpose = Unknown."),
    "reason": ("1 ligne = 1 motif de retour", "Motifs de retour", "Silver -> Gold dim_motif", "Descriptions aléatoires (non exploitables métier)."),
    "ship_mode": ("1 ligne = 1 mode de livraison", "Livraison web", "Silver -> Gold dim_livraison", "Toutes les colonnes descriptives sont aléatoires."),
    "web_page": ("1 ligne = 1 page web", "Typologie des pages", "Silver -> Gold dim_page", "60 pages, wp_type exploitable (8 valeurs)."),
    "web_site": ("1 ligne = 1 site web", "Référentiel site", "Silver -> Gold dim_site", "Absente du document de référence, présente dans le kit."),
}


def fmt_cols_with_nulls(r):
    cols = [f"{c['name']} ({c['null_pct']} %)" for c in r["columns"] if c["nulls"]]
    return ", ".join(cols[:8]) + (" …" if len(cols) > 8 else "") if cols else "aucune"


wb = Workbook()
wb.remove(wb.active)

# ------------------------------------------------------------------ feuille Kit
data_files = [r for r in prof if r["kit"] == "data"]
ref_files = [r for r in prof if r["kit"] == "data_refresh"]
for r in prof:
    if not r["file"].endswith(".dat"):
        r["spec_sf1_bytes"] = None
same = [r["table"] for r in data_files if r["spec_sf1_bytes"] and r["size_bytes"] == r["spec_sf1_bytes"]]
diff = [f"{r['table']} ({r['size_bytes'] - r['spec_sf1_bytes']:+,} octets / {100 * (r['size_bytes'] - r['spec_sf1_bytes']) / r['spec_sf1_bytes']:+.3f} %)".replace(",", " ")
        for r in data_files if r["spec_sf1_bytes"] and r["size_bytes"] != r["spec_sf1_bytes"]]
tot_d = sum(r["size_bytes"] for r in data_files)
tot_r = sum(r["size_bytes"] for r in ref_files)
sheet(wb, "Kit", ["Information", "Valeur constatée", "Statut"], [
    ["Nom du kit ou de l'archive", "retail_project.zip -> dossier retail_project/ (sous-dossiers data/ et data_refresh/)", "Vérifié"],
    ["Version", "Pas de numéro de version dans l'archive. D'après les tailles des fichiers : jeu TPCx-BB à l'échelle SF=1 (spécification v1.6.0).", "Déduit"],
    ["Provenance", "Fourni par le formateur. Structure, noms de tables et tailles conformes au jeu TPCx-BB à l'échelle SF=1 "
     f"(spécification TPCx-BB v1.6.0, Table 2-1) : {len(same)} fichiers sur 23 ont exactement la taille de référence.", "Déduit / À valider"],
    ["Date de mise à disposition", "16/11/2026 (récupération de l'archive). Fichiers de l'archive datés du 15/11/2026.", "Vérifié"],
    ["Source de téléchargement ou de distribution", "Archive transmise par le formateur.", "Vérifié"],
    ["Format des fichiers", "34 fichiers .dat : texte délimité par '|', sans ligne d'en-tête, fins de ligne CRLF, ASCII (sauf 917 lignes UTF-8 dans customer). 2 fichiers CSV d'audit (item_marketprices_audit.csv).", "Vérifié"],
    ["Volume total constaté", f"data/ : {tot_d:,} octets ({tot_d / 1e6:.1f} Mo) ; data_refresh/ : {tot_r:,} octets ({tot_r / 1e6:.1f} Mo) ; archive zip : 296 359 886 octets.".replace(",", " "), "Vérifié"],
    ["Nombre de fichiers", f"{len(prof)} fichiers : {len(data_files)} dans data/ (23 tables), {len(ref_files)} dans data_refresh/ (11 tables).", "Vérifié"],
    ["Nombre de lignes", f"data/ : {sum(r['rows'] for r in data_files if r['file'].endswith('.dat')):,} lignes ; data_refresh/ : {sum(r['rows'] for r in ref_files if r['file'].endswith('.dat')):,} lignes".replace(",", " "), "Vérifié"],
    ["Outil de génération", "PDGF, le générateur fourni avec TPCx-BB (le fichier item_marketprices_audit.csv est un rapport de génération).", "Déduit"],
    ["Écarts avec la référence SF=1", "Petits écarts de taille sur 9 fichiers : " + "; ".join(diff), "À valider"],
    ["Noms de colonnes", "Pas d'en-tête dans les fichiers : noms repris du schéma TPCx-BB ; le nombre de champs est vérifié sur 100 % des lignes de chaque fichier.", "Déduit"],
    ["Données complémentaires (hors TPCx-BB)", "Aucune fournie. Le dossier data_refresh/ fait partie du kit TPCx-BB (jeu de rafraîchissement).", "Vérifié"],
], {"Information": 34, "Valeur constatée": 100, "Statut": 22})

# ------------------------------------------------------------------ feuille Inventaire
inv_rows = []
for r in prof:
    n = NOTES.get(r["table"], ("", "", "", ""))
    is_dat = r["file"].endswith(".dat")
    kd = r.get("key_duplicates")
    inv_rows.append([
        r["kit"], r["domain"], r["table"], r["file"], f"retail_project/{r['kit']}/{r['table']}/{r['file']}",
        "texte délimité '|', sans en-tête" if is_dat else "CSV (virgule) – fichier d'audit",
        "CRLF" if r.get("crlf") else "LF", "UTF-8 (lignes non ASCII : %d)" % r["non_ascii_lines"] if r.get("non_ascii_lines") else "ASCII",
        r["size_bytes"], round(r["size_bytes"] / 1e6, 3), r.get("spec_sf1_bytes"), r["rows"],
        len(r["columns"]) if is_dat else "", ", ".join(r.get("candidate_key") or []) or ("aucune" if is_dat else ""),
        ("unique" if kd == 0 else f"{kd} doublons") if kd is not None else "", r.get("line_duplicates"),
        fmt_cols_with_nulls(r) if is_dat else "", n[0], n[1], n[2], n[3] if r["kit"] == "data" else "Jeu de rafraîchissement (voir feuille Refresh)",
        "Vérifié (taille, lignes, champs) ; noms de colonnes : Déduit", r["sha256"]])
sheet(wb, "Inventaire fichiers",
      ["Kit", "Domaine", "Table", "Fichier", "Chemin", "Format", "Fin de ligne", "Encodage", "Taille (octets)",
       "Taille (Mo)", "Taille réf. SF1 (octets)", "Nb lignes", "Nb colonnes", "Clé candidate", "Unicité clé",
       "Lignes en double", "Colonnes avec valeurs nulles (%)", "Grain", "Usage analytique envisagé",
       "Destination logique", "Qualité / anomalies", "Statut", "SHA-256"], inv_rows,
      {"Chemin": 40, "Colonnes avec valeurs nulles (%)": 45, "Grain": 34, "Usage analytique envisagé": 34,
       "Destination logique": 34, "Qualité / anomalies": 60, "SHA-256": 30, "Domaine": 16})

# ------------------------------------------------------------------ feuille Colonnes
SQL = {"int": "BIGINT / INT", "decimal": "DECIMAL(7,2)", "date": "DATE", "time": "STRING (HH:MM:SS)", "string": "STRING", "vide": "STRING (vide)"}
col_rows = []
for r in prof:
    for i, c in enumerate(r["columns"], 1):
        t = c["type_observed"]
        mix = "" if len(c["type_mix"]) <= 1 else " ; ".join(f"{k}={v}" for k, v in c["type_mix"].items())
        cible = "BIGINT (clé)" if c["name"].endswith("_sk") and t == "int" else SQL.get(t, t)
        if mix and "string" in c["type_mix"]:
            cible = "STRING"
        col_rows.append([r["kit"], r["table"], i, c["name"], t, mix, cible, c["nulls"], c["null_pct"],
                         c["min"], c["max"], c["distinct"] if c["distinct"] is not None else "> 500 000",
                         c["max_len"], " | ".join(c["samples"])])
sheet(wb, "Colonnes", ["Kit", "Table", "Pos.", "Colonne", "Type observé", "Mélange de types", "Type cible proposé",
                       "Nb nulls", "% nulls", "Min", "Max", "Nb distincts", "Long. max", "Exemples"], col_rows,
      {"Colonne": 28, "Exemples": 60, "Mélange de types": 24, "Type cible proposé": 18})

# ------------------------------------------------------------------ feuille Relations
rel_rows = []
for k, v in rel["integrite_referentielle"].items():
    statut = "Vérifié" if v["orphelins"] == 0 else "Vérifié – orphelins"
    rel_rows.append([k.split(" -> ")[0], k.split(" -> ")[1], "N:1", v["lignes"], v["nulls"], v["pct_nulls"],
                     v["orphelins"], ", ".join(v["exemples_orphelins"]), v["referentiel"], statut])
c = comp
extra = [
    ["data.store_returns.(sr_item_sk, sr_ticket_number)", "store_sales (ss_item_sk, ss_ticket_number)", "N:1 (ambigu si clé dupliquée)",
     rel["controles_arithmetiques_et_qualite"]["sr_lignes"], 0, 0, 0, f"{c['store_returns_chronologie']['cle_vente_ambigue(plusieurs lignes de vente)']} rattachements ambigus", "data", "Vérifié"],
    ["data.web_returns.(wr_item_sk, wr_order_number)", "web_sales (ws_item_sk, ws_order_number)", "N:1 (ambigu si clé dupliquée)",
     rel["controles_arithmetiques_et_qualite"]["wr_lignes"], 0, 0, 0, f"{c['web_returns_chronologie']['cle_vente_ambigue(plusieurs lignes de vente)']} rattachements ambigus", "data", "Vérifié"],
    ["data.web_clickstreams.(wcs_item_sk, wcs_sales_sk)", "web_sales (ws_item_sk, ws_order_number)", "N:1 (clics avec vente uniquement)",
     c["web_clickstreams_vs_ventes"]["clics_avec_wcs_sales_sk"], rel["controles_arithmetiques_et_qualite"]["wcs_lignes"] - c["web_clickstreams_vs_ventes"]["clics_avec_wcs_sales_sk"], 90.13, 0,
     "100 % des couples retrouvés dans web_sales, 1 % seulement dans store_sales (coïncidence de numéros) ; wcs_user_sk = ws_bill_customer_sk à 100 %", "data", "Vérifié (signification déduite)"],
    ["data.product_reviews.(pr_item_sk, pr_order_sk)", "web_sales (ws_item_sk, ws_order_number)", "N:1",
     c["product_reviews_vs_ventes"]["avis"], 0, 0, 0, f"100 % retrouvés dans web_sales ; pr_user_sk = client de la commande pour {c['product_reviews_vs_ventes']['pr_user_sk = ws_bill_customer_sk de la commande']} avis", "data", "Vérifié (signification déduite)"],
    ["data.store_sales.ss_ticket_number", "(transaction)", "1 ticket = 1 date, 1 magasin, 1 client",
     rel["cardinalites"]["store_sales_tickets_distincts"], 0, 0, rel["cardinalites"]["store_sales_tickets_incoherents(plusieurs date/magasin/client)"],
     f"{rel['cardinalites']['store_sales_lignes_par_ticket_moy']} lignes / ticket en moyenne (max {rel['cardinalites']['store_sales_lignes_par_ticket_max']})", "data", "Vérifié"],
    ["data.web_sales.ws_order_number", "(commande)", "1 commande = 1 date, 1 client facturé",
     rel["cardinalites"]["web_sales_commandes_distinctes"], 0, 0, 0,
     f"{rel['cardinalites']['web_sales_lignes_par_commande_moy']} lignes / commande en moyenne", "data", "Vérifié"],
    ["store_sales.ss_ticket_number vs web_sales.ws_order_number", "-", "aucune relation", "", "", "", "",
     "Mêmes plages de valeurs (0-89099) mais domaines distincts : ne jamais joindre ces deux colonnes", "data", "Déduit"],
]
sheet(wb, "Relations", ["Source (table.colonne)", "Cible", "Cardinalité", "Lignes testées", "Nulls", "% nulls",
                        "Orphelins", "Exemples / commentaire", "Référentiel utilisé", "Statut"], rel_rows + extra,
      {"Source (table.colonne)": 50, "Cible": 36, "Exemples / commentaire": 60, "Cardinalité": 24})

# ------------------------------------------------------------------ feuille Domaines (document de référence vs kit)
REF = [("Temps", "date_dim", "d_date_sk"), ("Temps", "time_dim", "t_time_sk"), ("Clients", "customer", "c_customer_sk"),
       ("Clients", "customer_address", "ca_address_sk"), ("Clients", "customer_demographics", "cd_demo_sk"),
       ("Clients", "household_demographics", "hd_demo_sk"), ("Produits", "item", "i_item_sk"),
       ("Magasins", "store", "s_store_sk"), ("Ventes magasin", "store_sales", "ticket + produit à contrôler"),
       ("Retours magasin", "store_returns", "ticket + produit à contrôler"), ("Ventes web", "web_sales", "ws_sk ; commande ws_order_number"),
       ("Retours web", "web_returns", "commande + produit à contrôler"), ("Stocks", "inventory", "date + produit + entrepôt"),
       ("Entrepôts", "warehouse", "w_warehouse_sk"), ("Promotions", "promotion", "p_promo_sk"),
       ("Navigation", "web_clickstreams", "wcs_click_sk"), ("Pages web", "web_page", "wp_web_page_sk"),
       ("Avis", "product_reviews", "pr_review_sk"), ("Prix concurrents", "item_marketprices", "imp_sk")]
present = {r["table"]: r for r in data_files}
OBS = {"store_sales": "(ss_item_sk, ss_ticket_number) NON unique : 4 038 doublons -> pas de clé naturelle au grain ligne",
       "store_returns": "(sr_item_sk, sr_ticket_number) : 158 doublons",
       "web_sales": "Colonne ws_sk ABSENTE. (ws_item_sk, ws_order_number) : 4 076 doublons",
       "web_returns": "(wr_item_sk, wr_order_number) : 150 doublons",
       "inventory": "(inv_date_sk, inv_item_sk, inv_warehouse_sk) unique",
       "web_clickstreams": "Colonne wcs_click_sk ABSENTE (6 colonnes seulement) : aucun identifiant de clic"}
dom_rows = [[d, t, k, "Oui" if t in present else "Non", OBS.get(t, f"{k} unique (vérifié)"),
             "Oui" if t in {r['table'] for r in ref_files} else "Non"] for d, t, k in REF]
for t in ("income_band", "reason", "ship_mode", "web_site"):
    dom_rows.append([NOTES and present[t]["domain"], t, "(absente du document)", "Oui", "Table présente dans le kit mais non listée dans le document de référence", "Non"])
sheet(wb, "Domaines vs référence", ["Domaine", "Table", "Clé (document de référence)", "Présente dans data/",
                                    "Clé constatée", "Présente dans data_refresh/"], dom_rows,
      {"Clé constatée": 70, "Clé (document de référence)": 32})

# ------------------------------------------------------------------ feuille Refresh
rr = []
for t, cnt in rel["data_refresh"].items():
    rr.append([t, cnt.get("lignes"), "; ".join(f"{k}={v}" for k, v in cnt.items() if k != "lignes")])
for t in ("store_sales", "web_sales", "web_clickstreams"):
    p = comp[f"periode_{t}"]
    rr.append([t + " (période)", "", f"data : {p['data'][0]} -> {p['data'][1]} ; refresh : {p['data_refresh'][0]} -> {p['data_refresh'][1]} ; jour commun : {', '.join(p['jours_communs'])}"])
sheet(wb, "Refresh", ["Table", "Lignes", "Constats"], rr, {"Constats": 110, "Table": 28})

out = os.path.join(PRE, "02_inventaire_sources.xlsx")
wb.save(out)
print("écrit :", out)

# ================================================================== dictionnaire KPI
k = rel["kpi_de_test_par_annee"]
ret_q_s = sum(v["quantite"] for n, v in k.items() if n.startswith("retours_magasin"))
ret_q_w = sum(v["quantite"] for n, v in k.items() if n.startswith("retours_web"))
sold_s = sum(v["quantite"] for n, v in k.items() if n.startswith("magasin_"))
sold_w = sum(v["quantite"] for n, v in k.items() if n.startswith("web_"))
m04, w04, m03, w03 = k["magasin_2004"], k["web_2004"], k["magasin_2003"], k["web_2003"]
cs = comp["web_clickstreams_vs_ventes"]
stock = list(comp["kpi_stock"].items())[0]  # premier relevé complet (le dernier est réparti entre data et data_refresh)
eur = lambda x: f"{x:,.2f}".replace(",", " ")  # noqa: E731

KPI = [
    ["K01", "Chiffre d'affaires net magasin", "Montant encaissé sur les ventes en magasin, après remises et coupons, hors taxes, retours non déduits.",
     "SUM(ss_net_paid)", "Dollar ($)", "Canal magasin, 12 magasins, 2001-01-01 -> 2005-12-13 (+ refresh jusqu'au 2005-12-31)",
     "Jour x magasin x produit", "Quotidienne (agrégats mensuels / annuels)", "store_sales (ss_net_paid, ss_sold_date_sk, ss_store_sk, ss_item_sk), date_dim, store, item",
     "Pas de colonne devise (dollar retenu)", "HT ; ne déduit pas les retours (voir K10). Année 2005 incomplète dans data/.", "Indispensable", "Calculable", f"2004 : {eur(m04['net_paid'])}"],
    ["K02", "Chiffre d'affaires net web", "Montant encaissé sur les commandes web, après remises et coupons, hors taxes et hors frais de port.",
     "SUM(ws_net_paid)", "$", "Canal web, 30 sites, même période", "Jour x site x produit", "Quotidienne",
     "web_sales (ws_net_paid, ws_sold_date_sk, ws_web_site_sk, ws_item_sk), date_dim, item", "Pas de colonne devise (dollar retenu)",
     "Ne pas additionner avec ws_net_paid_inc_ship (frais de port).", "Indispensable", "Calculable", f"2004 : {eur(w04['net_paid'])}"],
    ["K03", "Nombre de transactions", "Nombre de tickets de caisse (magasin) ou de commandes (web) distincts.",
     "COUNT(DISTINCT ss_ticket_number) ; COUNT(DISTINCT ws_order_number)", "Nombre", "Par canal (jamais mélanger les deux identifiants)",
     "Jour x magasin / site", "Quotidienne", "store_sales.ss_ticket_number ; web_sales.ws_order_number", "-",
     "Une transaction ≠ une ligne de vente (≈ 7,5 lignes par ticket). Les numéros de ticket et de commande partagent la même plage de valeurs.",
     "Indispensable", "Calculable", f"2004 : magasin {m04['transactions_distinctes']} ; web {w04['transactions_distinctes']}"],
    ["K04", "Panier moyen", "Montant moyen dépensé par transaction.", "K01 / K03 (magasin) ; K02 / K03 (web)", "$ / transaction",
     "Même périmètre au numérateur et au dénominateur", "Mois x canal (x magasin)", "Mensuelle", "store_sales, web_sales", "-",
     f"Valeurs très élevées (≈ {eur(m04['net_paid'] / m04['transactions_distinctes'])} en magasin) : quantités jusqu'à 100 par ligne, données synthétiques.",
     "Indispensable", "Calculable", f"2004 : magasin {eur(m04['net_paid'] / m04['transactions_distinctes'])} ; web {eur(w04['net_paid'] / w04['transactions_distinctes'])}"],
    ["K05", "Quantités vendues", "Nombre d'unités vendues.", "SUM(ss_quantity) ; SUM(ws_quantity)", "Unités", "Par canal / produit / catégorie",
     "Jour x produit x lieu", "Quotidienne", "store_sales.ss_quantity, web_sales.ws_quantity, item", "Unité de mesure produit (i_units aléatoire)",
     "Additionner des unités de produits différents n'a de sens qu'à titre indicatif.", "Indispensable", "Calculable", f"2004 : magasin {int(m04['quantite']):,} ; web {int(w04['quantite']):,}".replace(",", " ")],
    ["K06", "Évolution des ventes N / N-1", "Variation relative du CA net entre deux périodes comparables.",
     "(K01_N - K01_N-1) / K01_N-1 x 100", "%", "Périodes de même durée (ex. 2004 vs 2003 ; 2005 seulement jusqu'au 13/12 sans refresh)", "Mois / année x canal",
     "Mensuelle", "store_sales, web_sales, date_dim", "-", "Comparer des périodes complètes ; corrélation ≠ causalité.", "Indispensable", "Calculable",
     f"2004 vs 2003 : magasin {100 * (m04['net_paid'] - m03['net_paid']) / m03['net_paid']:+.2f} % ; web {100 * (w04['net_paid'] - w03['net_paid']) / w03['net_paid']:+.2f} %"],
    ["K07", "Taux de remise", "Part de la remise accordée par rapport au prix catalogue.", "SUM(ss_ext_discount_amt) / SUM(ss_ext_list_price) x 100", "%",
     "Par canal / promotion / catégorie", "Mois x canal", "Mensuelle", "store_sales / web_sales (ext_discount_amt, ext_list_price), promotion", "-",
     "≈ 50 % sur tout le jeu (prix de vente tiré entre 0 et le prix catalogue) : non représentatif d'un distributeur réel.", "Utile", "Calculable",
     f"2004 : magasin {m04['taux_remise_pct']} % ; web {w04['taux_remise_pct']} %"],
    ["K08", "Marge brute et taux de marge", "Résultat après coût d'achat des marchandises.", "SUM(ss_net_profit) ; SUM(ss_net_profit) / SUM(ss_net_paid) x 100",
     "$ ; %", "Par canal / produit", "Mois x produit", "Mensuelle", "store_sales.ss_net_profit (= net_paid - ext_wholesale_cost, vérifié)", "Coûts logistiques, frais fixes",
     "Marge négative sur l'ensemble (74 % des lignes) : artefact de génération ; à présenter avec réserve.", "Utile", "Calculable (fiabilité métier faible)",
     f"2004 magasin : {eur(m04['marge'])} ({100 * m04['marge'] / m04['net_paid']:.1f} %)"],
    ["K09", "Taux de retour (quantités)", "Part des unités vendues qui sont retournées.", "SUM(sr_return_quantity) / SUM(ss_quantity) x 100 (rattachement par produit + ticket)",
     "%", "Par canal / produit / motif ; rattacher les retours à la période de vente", "Mois de vente x produit", "Mensuelle",
     "store_returns, store_sales, web_returns, web_sales, reason", "Motifs de retour lisibles (r_reason_desc aléatoire)",
     "Retours jusqu'à 2 ans après la vente (2006-2008) : taux d'une période récente sous-estimé.", "Indispensable", "Calculable",
     f"Global : magasin {100 * ret_q_s / sold_s:.2f} % ; web {100 * ret_q_w / sold_w:.2f} %"],
    ["K10", "CA net de retours", "CA après déduction des montants remboursés.", "K01 - SUM(sr_return_amt) (idem web)", "$",
     "Par canal, retours affectés à la période de vente ou de retour (à décider)", "Mois x canal", "Mensuelle", "store_sales, store_returns, web_sales, web_returns",
     "Règle d'affectation temporelle", "Ne pas soustraire sr_net_loss (inclut frais) sans règle métier.", "Utile", "Calculable",
     f"Retours magasin 2004 (date de retour) : {eur(k['retours_magasin_2004']['montant_retour'])}"],
    ["K11", "Stock disponible", "Quantité en stock à une date de relevé.", "SUM(inv_quantity_on_hand) à une date donnée (pas de somme dans le temps)",
     "Unités", "Par produit x entrepôt, 5 entrepôts, relevé hebdomadaire", "Semaine x produit x entrepôt", "Hebdomadaire",
     "inventory, item, warehouse, date_dim (+ data_refresh/item pour 180 produits)", "Mouvements d'entrée / sortie, stock magasin",
     "Mesure semi-additive. Le stock est par entrepôt, pas par magasin. Le relevé du 2005-12-12 est réparti entre data/ (35 100 lignes) et data_refresh/ (54 900).", "Utile", "Calculable",
     f"Relevé {stock[0].replace('releve_', '')} : {stock[1].get('qte_totale', 0):,} unités".replace(",", " ")],
    ["K12", "Taux de rupture", "Part des couples produit x entrepôt sans stock à une date.", "COUNT(inv_quantity_on_hand = 0) / COUNT(*) x 100",
     "%", "Par entrepôt / catégorie", "Semaine x entrepôt", "Hebdomadaire", "inventory", "Seuil d'alerte, demande non servie",
     "Les quantités vides (0,026 %) ne doivent pas être comptées comme ruptures.", "Utile", "Calculable",
     f"Relevé {stock[0].replace('releve_', '')} : {100 * stock[1].get('qte_zero', 0) / stock[1]['lignes']:.3f} %"],
    ["K13", "Part du web dans le CA", "Poids du canal web dans le CA total.", "K02 / (K01 + K02) x 100", "%", "Tous canaux disponibles (magasin + web)",
     "Mois", "Mensuelle", "store_sales, web_sales", "Canal catalogue absent du kit", "Pas d'autres canaux dans le kit.", "Utile", "Calculable",
     f"2004 : {100 * w04['net_paid'] / (w04['net_paid'] + m04['net_paid']):.1f} %"],
    ["K14", "Part des clics liés à un achat", "Part des clics de navigation associés à une ligne de commande web.", "COUNT(wcs_sales_sk NOT NULL) / COUNT(*) x 100",
     "%", "Navigation web", "Jour x page", "Quotidienne", "web_clickstreams", "Identifiant de session, panier, événements « ajout au panier »",
     "N'est PAS un taux de conversion (pas de session). Un clic n'est ni un ajout au panier ni un achat.", "Complémentaire", "Partiellement calculable",
     f"Global : {100 * cs['clics_avec_wcs_sales_sk'] / rel['controles_arithmetiques_et_qualite']['wcs_lignes']:.2f} %"],
    ["K15", "Note moyenne des avis", "Satisfaction exprimée par les avis produits.", "AVG(pr_review_rating)", "Note / 5", "Produits ayant des avis (16 742 produits)",
     "Mois x produit", "Mensuelle", "product_reviews, item", "Volume d'avis par produit faible", "Biais d'auto-sélection des avis ; texte synthétique.", "Complémentaire", "Calculable",
     f"Global : {comp['kpi_avis']['note_moyenne']} / 5 ({comp['kpi_avis']['nb_avis']} avis)"],
    ["K16", "CA par m² de surface de vente", "Productivité commerciale des magasins.", "K01 / s_floor_space", "$ / m²", "Par magasin",
     "Année x magasin", "Annuelle", "store_sales, store.s_floor_space", "Surface fiable (s_floor_space vaut 5,8 M à 8,9 M)",
     "Valeurs de surface peu plausibles -> indicateur non fiable.", "Complémentaire", "Non fiable (à valider)", "-"],
    ["K17", "Écart de prix vs concurrence", "Positionnement prix par rapport aux concurrents.", "AVG(i_current_price - imp_competitor_price) sur la période de validité",
     "$ ; %", "Produits ayant un prix concurrent", "Produit x période", "Hebdomadaire", "item, item_marketprices", "Identité réelle des concurrents",
     "Concurrents codés ; i_current_price n'est pas historisé (pas de SCD).", "Complémentaire", "Partiellement calculable", "-"],
    ["K18", "Taux de conversion visiteurs", "Part des visiteurs qui achètent.", "Visiteurs acheteurs / visiteurs", "%", "Web", "Jour", "Quotidienne", "web_clickstreams",
     "Identifiant de session / visite ; 42 % des clics sans utilisateur", "Non calculable de façon fiable : besoin non couvert, source complémentaire nécessaire (logs de session).",
     "Utile", "Non calculable", "-"],
]
wb2 = Workbook()
wb2.remove(wb2.active)
sheet(wb2, "Dictionnaire KPI", ["ID", "Nom", "Définition métier", "Formule", "Unité", "Périmètre", "Granularité", "Fréquence",
                                "Sources nécessaires", "Données manquantes", "Limites d'interprétation", "Priorité",
                                "Calculabilité", "Valeur de test (preuve)"], KPI,
      {"Nom": 28, "Définition métier": 40, "Formule": 40, "Périmètre": 32, "Sources nécessaires": 42,
       "Données manquantes": 30, "Limites d'interprétation": 50, "Valeur de test (preuve)": 34})
yr = []
for name, v in k.items():
    canal, an = name.rsplit("_", 1)
    yr.append([canal, an, v.get("lignes"), v.get("transactions_distinctes"), v.get("ca_ext_sales_price"), v.get("net_paid"),
               v.get("quantite"), v.get("panier_moyen_ext_sales"), v.get("taux_remise_pct"), v.get("marge"), v.get("montant_retour")])
sheet(wb2, "Valeurs de test par année", ["Canal", "Année", "Lignes", "Transactions", "CA brut (ext_sales_price)", "CA net (net_paid)",
                                         "Quantité", "Panier moyen (CA brut)", "Taux de remise %", "Marge", "Montant retourné"], yr)
sheet(wb2, "CA par catégorie (magasin)", ["Catégorie", "CA brut 2001-2005"], rel["top10_categories_ca_magasin"], {"Catégorie": 30})
sheet(wb2, "CA par magasin", ["s_store_sk", "CA brut 2001-2005"], list(rel["ca_magasin_par_store_sk"].items()))
out = os.path.join(PRE, "08_dictionnaire_KPI.xlsx")
wb2.save(out)
print("écrit :", out)
