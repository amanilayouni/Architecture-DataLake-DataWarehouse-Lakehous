"""Rapport texte des contrôles qualité (à partir des sorties des scripts 01, 02 et 03).

Usage : python 05_rapport_qualite.py   ->  ../03_rapport_controles_qualite.txt
"""
import json
import os

PRE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
prof = json.load(open(os.path.join(PRE, "05_profil_fichiers.json"), encoding="utf-8"))
rel = json.load(open(os.path.join(PRE, "06_relations_controles.json"), encoding="utf-8"))
comp = json.load(open(os.path.join(PRE, "07_controles_complementaires.json"), encoding="utf-8"))
L = []


def p(s=""):
    L.append(s)


def n(x):
    return f"{x:,}".replace(",", " ")


p("RAPPORT DES CONTRÔLES QUALITÉ - KIT TPCx-BB (retail_project)")
p("Lecture complète des fichiers (pas d'échantillon). Valeur nulle = champ vide entre deux '|'.")
p()
p("1. FICHIERS, LIGNES ET STRUCTURE")
p(f"{'kit':<13}{'fichier':<30}{'octets':>14}{'lignes':>12}{'col.':>6}  structure")
for r in prof:
    if not r["file"].endswith(".dat"):
        p(f"{r['kit']:<13}{r['file']:<30}{n(r['size_bytes']):>14}{n(r['rows']):>12}{'':>6}  fichier d'audit CSV")
        continue
    h = r["field_count_histogram"]
    ok = "OK" if list(h) == [str(r["expected_fields"])] or list(h) == [r["expected_fields"]] else f"KO {h}"
    p(f"{r['kit']:<13}{r['file']:<30}{n(r['size_bytes']):>14}{n(r['rows']):>12}{len(r['columns']):>6}  {ok} (nb de champs constant)")
p()
p("2. VALEURS NULLES (colonnes avec au moins une valeur vide, lot data/)")
for r in prof:
    if r["kit"] != "data" or not r["columns"]:
        continue
    cols = [c for c in r["columns"] if c["nulls"]]
    if cols:
        p(f"  {r['table']}")
        for c in sorted(cols, key=lambda c: -c["nulls"])[:8]:
            p(f"      {c['name']:<30}{n(c['nulls']):>12}  ({c['null_pct']} %)")
        if len(cols) > 8:
            p(f"      ... et {len(cols) - 8} autres colonnes avec moins de {sorted(cols, key=lambda c: -c['nulls'])[8]['null_pct']} % de vides")
    else:
        p(f"  {r['table']:<28} aucune valeur vide")
p()
p("3. DOUBLONS")
for r in prof:
    if not r["file"].endswith(".dat"):
        continue
    key = ", ".join(r["candidate_key"] or []) or "(pas de clé)"
    kd = r["key_duplicates"]
    p(f"  {r['kit']:<13}{r['table']:<24} clé {key:<48} doublons de clé : {'-' if kd is None else n(kd):>6}"
      f"   lignes identiques : {'-' if r['line_duplicates'] is None else n(r['line_duplicates'])}")
p()
p("4. COHÉRENCE DES MONTANTS ET DES DATES (lot data/)")
a = rel["controles_arithmetiques_et_qualite"]
for k, v in a.items():
    p(f"  {k:<45}{n(v):>12}")
for t in ("store_returns_chronologie", "web_returns_chronologie"):
    p(f"  {t}")
    for k, v in comp[t].items():
        p(f"      {k:<45}{v}")
p()
p("5. INTÉGRITÉ RÉFÉRENTIELLE (valeurs sans correspondance dans la table de référence)")
for k, v in rel["integrite_referentielle"].items():
    p(f"  {k:<72} nulls {n(v['nulls']):>10}   orphelins {n(v['orphelins']):>8}")
p()
p("6. RATTACHEMENTS PAR CLÉ COMPOSITE")
for t in ("web_clickstreams_vs_ventes", "product_reviews_vs_ventes", "inventory_orphelins_vs_refresh", "data_refresh_rattachement_aux_ventes"):
    p(f"  {t}")
    for k, v in comp[t].items():
        p(f"      {k:<75}{n(v) if isinstance(v, int) else v}")
p()
p("7. CARDINALITÉS")
for k, v in rel["cardinalites"].items():
    p(f"  {k:<70}{v}")

out = os.path.join(PRE, "03_rapport_controles_qualite.txt")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("écrit :", out, len(L), "lignes")
