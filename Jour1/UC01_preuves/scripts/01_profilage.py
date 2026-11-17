"""UC-01 – Étape C : inventaire et profilage des fichiers TPCx-BB réellement fournis.

Usage :
    python 01_profilage.py <racine_kit> <dossier_sortie>
    ex. python 01_profilage.py "C:/Users/msi/Downloads/retail_project/retail_project" ..

Produit dans <dossier_sortie> :
    05_profil_fichiers.json   profil complet (taille, sha256, lignes, champs, colonnes, types, nulls, clés...)
    04_profil_colonnes.csv    une ligne par colonne
    01_arborescence_kit.txt   arborescence du kit avec tailles
    apercus_fichiers/*.txt   5 premières lignes de chaque fichier, avec les noms de colonnes
Les fichiers sont lus en flux (ligne à ligne) : aucune donnée n'est modifiée.
"""
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from tpcxbb_schema import CANDIDATE_KEYS, DOMAINS, SCHEMA, SPEC_SF1_BYTES  # noqa: E402

DISTINCT_CAP = 500_000
RE_DEC = re.compile(r"-?\d+\.\d+$")
RE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")
RE_TIME = re.compile(r"\d{2}:\d{2}:\d{2}$")


def classify(v):
    if v.isdigit() or (v[:1] == "-" and v[1:].isdigit()):
        return "int"
    if RE_DEC.match(v):
        return "decimal"
    if RE_DATE.match(v):
        return "date"
    if RE_TIME.match(v):
        return "time"
    return "string"


def new_col():
    return {"nulls": 0, "types": Counter(), "min": None, "max": None, "distinct": set(), "capped": False,
            "max_len": 0, "samples": []}


def update_col(c, v):
    if v == "":
        c["nulls"] += 1
        return
    t = classify(v)
    c["types"][t] += 1
    if t in ("int", "decimal"):
        x = int(v) if t == "int" else float(v)
        if c["min"] is None or x < c["min"]:
            c["min"] = x
        if c["max"] is None or x > c["max"]:
            c["max"] = x
    elif t in ("date", "time"):
        if c["min"] is None or (isinstance(c["min"], str) and v < c["min"]):
            c["min"] = v
        if c["max"] is None or (isinstance(c["max"], str) and v > c["max"]):
            c["max"] = v
    if len(v) > c["max_len"]:
        c["max_len"] = len(v)
    if not c["capped"]:
        c["distinct"].add(v if len(v) <= 64 else hashlib.md5(v.encode()).digest())
        if len(c["distinct"]) > DISTINCT_CAP:
            c["capped"] = True
            c["distinct"] = set()
    if len(c["samples"]) < 3 and v not in c["samples"]:
        c["samples"].append(v[:80])


def profile(args):
    path, kit, table = args
    t0 = time.time()
    names = SCHEMA.get(table)
    is_dat = path.endswith(".dat")
    res = {"kit": kit, "table": table, "file": os.path.basename(path), "path": path,
           "format": "texte délimité '|' (sans en-tête)" if is_dat else "CSV (virgule)",
           "size_bytes": os.path.getsize(path), "spec_sf1_bytes": SPEC_SF1_BYTES.get(table) if kit == "data" else None,
           "domain": DOMAINS.get(table, "?")}
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    res["sha256"] = sha.hexdigest()

    if not is_dat:  # fichier d'audit CSV : simple relevé
        with open(path, "rb") as f:
            raw = f.read()
        txt = raw.decode("utf-8", errors="replace")
        lines = txt.splitlines()
        res.update({"rows": len(lines), "crlf": b"\r\n" in raw, "first_lines": lines[:6], "columns": []})
        return res

    cols = [new_col() for _ in names] if names else []
    field_counts = Counter()
    rows = crlf = non_ascii_lines = 0
    preview = []
    key_cols = CANDIDATE_KEYS.get(table)
    key_idx = [names.index(k) for k in key_cols] if key_cols else None
    key_set, key_dups, key_null = set(), 0, 0
    sorted_by_first, prev_first = True, None
    line_hashes, line_dups = set(), 0
    check_line_dups = res["size_bytes"] < 250_000_000

    with open(path, "rb") as f:
        for raw in f:
            rows += 1
            if raw.endswith(b"\r\n"):
                crlf += 1
            try:
                line = raw.decode("ascii").rstrip("\r\n")
            except UnicodeDecodeError:
                non_ascii_lines += 1
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if len(preview) < 5:
                preview.append(line if len(line) <= 400 else line[:400] + " …[tronqué]")
            if check_line_dups:
                h = hash(line)
                if h in line_hashes:
                    line_dups += 1
                else:
                    line_hashes.add(h)
            parts = line.split("|")
            n = len(parts)
            field_counts[n] += 1
            if n != len(cols):
                continue
            for c, v in zip(cols, parts):
                update_col(c, v)
            if key_idx:
                k = tuple(parts[i] for i in key_idx)
                if "" in k:
                    key_null += 1
                    continue
                if table == "inventory":  # trop gros pour un set global : contrôle par date si le fichier est trié
                    if k[0] != prev_first:
                        if prev_first is not None and int(k[0]) < int(prev_first):
                            sorted_by_first = False
                        prev_first = k[0]
                        key_set = set()
                if k in key_set:
                    key_dups += 1
                else:
                    key_set.add(k)

    out_cols = []
    for name, c in zip(names or [], cols):
        filled = sum(c["types"].values())
        dominant = c["types"].most_common(1)[0][0] if filled else "vide"
        out_cols.append({
            "name": name, "nulls": c["nulls"], "null_pct": round(100 * c["nulls"] / rows, 3) if rows else 0,
            "type_observed": dominant, "type_mix": dict(c["types"]),
            "min": c["min"], "max": c["max"], "max_len": c["max_len"],
            "distinct": None if c["capped"] else len(c["distinct"]), "distinct_capped": c["capped"],
            "samples": c["samples"]})
    res.update({
        "rows": rows, "crlf": crlf == rows, "non_ascii_lines": non_ascii_lines,
        "expected_fields": len(names) if names else None, "field_count_histogram": dict(field_counts),
        "columns": out_cols, "preview": preview,
        "line_duplicates": line_dups if check_line_dups else None,
        "candidate_key": key_cols, "key_duplicates": key_dups if key_idx else None,
        "key_nulls": key_null if key_idx else None,
        "key_check_mode": ("par date (fichier trié par inv_date_sk : %s)" % sorted_by_first) if table == "inventory"
        else ("global" if key_idx else None),
        "elapsed_s": round(time.time() - t0, 1)})
    return res


def main():
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(out, "apercus_fichiers"), exist_ok=True)
    jobs, tree = [], []
    for kit in ("data", "data_refresh"):
        kdir = os.path.join(root, kit)
        tree.append(f"{kit}/")
        for table in sorted(os.listdir(kdir)):
            tree.append(f"  {table}/")
            for fn in sorted(os.listdir(os.path.join(kdir, table))):
                p = os.path.join(kdir, table, fn)
                tree.append(f"    {fn:<36} {os.path.getsize(p):>13,} octets".replace(",", " "))
                jobs.append((p, kit, table))
    with open(os.path.join(out, "01_arborescence_kit.txt"), "w", encoding="utf-8") as f:
        f.write(f"Racine : {root}\n\n" + "\n".join(tree) + "\n")

    jobs.sort(key=lambda j: -os.path.getsize(j[0]))
    with Pool(3) as pool:
        results = pool.map(profile, jobs, chunksize=1)
    results.sort(key=lambda r: (r["kit"], r["table"], r["file"]))

    with open(os.path.join(out, "05_profil_fichiers.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(out, "04_profil_colonnes.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["kit", "table", "position", "colonne", "type_observe", "nb_nulls", "pct_nulls", "min", "max",
                    "nb_distinct", "longueur_max", "exemples"])
        for r in results:
            for i, c in enumerate(r["columns"], 1):
                w.writerow([r["kit"], r["table"], i, c["name"], c["type_observed"], c["nulls"], c["null_pct"],
                            c["min"], c["max"], c["distinct"] if c["distinct"] is not None else f">{DISTINCT_CAP}",
                            c["max_len"], " | ".join(c["samples"])])
    for r in results:
        with open(os.path.join(out, "apercus_fichiers", f"{r['kit']}__{r['file']}.txt"), "w", encoding="utf-8") as f:
            f.write(f"# {r['path']}\n# {r['size_bytes']} octets, {r['rows']} lignes\n")
            if r["columns"]:
                f.write("# colonnes (schéma TPCx-BB) : " + "|".join(c["name"] for c in r["columns"]) + "\n")
                f.write("\n".join(r["preview"]) + "\n")
            else:
                f.write("\n".join(r.get("first_lines", [])) + "\n")
    for r in results:
        print(f"{r['kit']:<13}{r['file']:<34}{r['size_bytes']:>12} o {r['rows']:>10} l  "
              f"champs={r.get('field_count_histogram')}  dup_cle={r.get('key_duplicates')}  {r.get('elapsed_s')}s")


if __name__ == "__main__":
    main()
