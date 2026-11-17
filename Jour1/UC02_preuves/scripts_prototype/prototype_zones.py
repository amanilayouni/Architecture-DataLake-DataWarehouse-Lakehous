"""Prototype local des zones Bronze / Silver / Gold (Python + Parquet, sans Hadoop ni Spark).

But : tester sur mon poste l'organisation des données prévue dans l'architecture, sur un périmètre réduit
(ventes magasin + référentiels item, store, date_dim), avant la mise en place de HDFS / NiFi / Spark.

Usage : python prototype_zones.py <racine_kit> <dossier_datalake>
"""
import csv
import hashlib
import os
import shutil
import sys
import time
from datetime import date

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "UC01_preuves", "scripts"))
from tpcxbb_schema import SCHEMA  # noqa: E402

KIT, LAKE = sys.argv[1], sys.argv[2]
INGEST_DATE = date.today().isoformat()
RUN_ID = time.strftime("%Y%m%d_%H%M%S")
TABLES = [("data", "store_sales"), ("data_refresh", "store_sales"), ("data", "item"), ("data_refresh", "item"),
          ("data", "store"), ("data", "date_dim")]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ------------------------------------------------------------------ 1. Bronze : copie fidèle + journal d'ingestion
log(f"run {RUN_ID} - zone BRONZE")
os.makedirs(os.path.join(LAKE, "_meta"), exist_ok=True)
journal = os.path.join(LAKE, "_meta", "journal_ingestion.csv")
new = not os.path.exists(journal)
with open(journal, "a", newline="", encoding="utf-8") as jf:
    w = csv.writer(jf, delimiter=";")
    if new:
        w.writerow(["run_id", "kit", "table", "fichier_source", "chemin_bronze", "octets", "sha256", "controle"])
    for kit, table in TABLES:
        src = os.path.join(KIT, kit, table, f"{table}.dat")
        dst_dir = os.path.join(LAKE, "bronze", "tpcxbb", table, f"kit={kit}", f"ingest_date={INGEST_DATE}")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, f"{table}.dat")
        shutil.copyfile(src, dst)
        h_src, h_dst = sha256(src), sha256(dst)
        ok = "OK" if h_src == h_dst else "ECHEC"
        w.writerow([RUN_ID, kit, table, src, os.path.relpath(dst, LAKE), os.path.getsize(dst), h_dst, ok])
        log(f"  {kit}/{table}.dat -> bronze ({os.path.getsize(dst):,} octets - sha256 {ok})".replace(",", " "))


def read_bronze(table, kit):
    p = os.path.join(LAKE, "bronze", "tpcxbb", table, f"kit={kit}", f"ingest_date={INGEST_DATE}", f"{table}.dat")
    names = SCHEMA[table]
    t = pacsv.read_csv(p, read_options=pacsv.ReadOptions(column_names=names),
                       parse_options=pacsv.ParseOptions(delimiter="|"),
                       convert_options=pacsv.ConvertOptions(strings_can_be_null=True, null_values=[""]))
    n = t.num_rows
    t = t.append_column("_kit", pa.array([kit] * n)).append_column("_source_file", pa.array([f"{table}.dat"] * n))
    return t.append_column("_ingest_ts", pa.array([RUN_ID] * n))


# ------------------------------------------------------------------ 2. Silver : typage, contrôles, Parquet partitionné
log("zone SILVER")
dates = read_bronze("date_dim", "data").select(["d_date_sk", "d_date", "d_year", "d_moy"])
item = pa.concat_tables([read_bronze("item", "data"), read_bronze("item", "data_refresh")])
store = read_bronze("store", "data")
sales = pa.concat_tables([read_bronze("store_sales", "data"), read_bronze("store_sales", "data_refresh")])
log(f"  store_sales lu : {sales.num_rows:,} lignes ({sales.num_columns} colonnes avec les colonnes techniques)".replace(",", " "))

# clé technique de ligne (le couple produit + ticket n'est pas unique)
sales = sales.append_column("ligne_id", pa.array(range(sales.num_rows), pa.int64()))
# contrôles qualité
known_items = item.column("i_item_sk")
bad_key = pc.or_(pc.is_null(sales["ss_ticket_number"]), pc.is_null(sales["ss_item_sk"]))
orphan = pc.invert(pc.is_in(sales["ss_item_sk"], value_set=known_items))
bad_amount = pc.greater(pc.abs(pc.subtract(sales["ss_ext_sales_price"],
                                           pc.multiply(sales["ss_sales_price"], pc.cast(sales["ss_quantity"], pa.float64())))), 0.011)
reject = pc.or_(pc.or_(bad_key, orphan), bad_amount)
quarantine, sales_ok = sales.filter(reject), sales.filter(pc.invert(reject))
log(f"  contrôles : clé nulle={pc.sum(bad_key).as_py()}, produit absent du référentiel={pc.sum(orphan).as_py()}, "
    f"montant incohérent={pc.sum(bad_amount).as_py()} -> {quarantine.num_rows} ligne(s) en quarantaine")
if quarantine.num_rows:
    os.makedirs(os.path.join(LAKE, "quarantine", "store_sales"), exist_ok=True)
    pq.write_table(quarantine, os.path.join(LAKE, "quarantine", "store_sales", f"run_id={RUN_ID}.parquet"))

sales_ok = sales_ok.join(dates, keys="ss_sold_date_sk", right_keys="d_date_sk", join_type="left outer")
sales_ok = sales_ok.rename_columns([{"d_year": "annee", "d_moy": "mois"}.get(c, c) for c in sales_ok.column_names])
silver_dir = os.path.join(LAKE, "silver", "store_sales")
shutil.rmtree(silver_dir, ignore_errors=True)
pq.write_to_dataset(sales_ok, silver_dir, partition_cols=["annee"], compression="snappy")
for name, t in [("item", item), ("store", store), ("date_dim", dates)]:
    d = os.path.join(LAKE, "silver", name)
    os.makedirs(d, exist_ok=True)
    pq.write_table(t, os.path.join(d, f"{name}.parquet"), compression="snappy")
log(f"  silver/store_sales écrit : {sales_ok.num_rows:,} lignes - partitionné par annee".replace(",", " "))

# ------------------------------------------------------------------ 3. Gold : agrégat KPI mensuel par magasin
log("zone GOLD")
s = pq.read_table(silver_dir)
s = s.set_column(s.column_names.index("annee"), "annee", pa.chunked_array([c.dictionary_decode() for c in s["annee"].chunks]))
g = s.group_by(["annee", "mois", "ss_store_sk"]).aggregate([
    ("ss_net_paid", "sum"), ("ss_ticket_number", "count_distinct"), ("ss_quantity", "sum"), ("ss_ext_discount_amt", "sum"),
    ("ss_ext_list_price", "sum")])
g = g.rename_columns(["annee", "mois", "s_store_sk", "ca_net", "nb_transactions", "quantite", "remise", "montant_liste"])
for c in ("ca_net", "remise", "montant_liste"):
    g = g.set_column(g.column_names.index(c), c, pc.round(g[c], 2))
g = g.append_column("panier_moyen", pc.round(pc.divide(g["ca_net"], pc.cast(g["nb_transactions"], pa.float64())), 2))
g = g.append_column("taux_remise_pct", pc.round(pc.multiply(pc.divide(g["remise"], g["montant_liste"]), 100), 2))
g = g.join(store.select(["s_store_sk", "s_store_name"]), keys="s_store_sk").sort_by([("annee", "ascending"), ("mois", "ascending"), ("s_store_sk", "ascending")])
gold_dir = os.path.join(LAKE, "gold", "kpi_mensuel_magasin")
os.makedirs(gold_dir, exist_ok=True)
pq.write_table(g, os.path.join(gold_dir, "kpi_mensuel_magasin.parquet"))
pacsv.write_csv(g, os.path.join(gold_dir, "kpi_mensuel_magasin.csv"))
log(f"  gold/kpi_mensuel_magasin : {g.num_rows} lignes (mois x magasin)")

# contrôle de réconciliation Silver <-> Gold
tot_silver = round(pc.sum(s["ss_net_paid"]).as_py(), 2)
tot_gold = round(pc.sum(g["ca_net"]).as_py(), 2)
log(f"  réconciliation CA net : silver={tot_silver:,.2f}  gold={tot_gold:,.2f}  -> {'OK' if abs(tot_silver - tot_gold) < 1 else 'ECART'}".replace(",", " "))
y2004 = pc.sum(g.filter(pc.equal(g["annee"], 2004))["ca_net"]).as_py()
log(f"  CA net magasin 2004 (gold) = {y2004:,.2f}  (valeur attendue d'après l'exploration UC-01 : 234 344 934.29)".replace(",", " "))


# ------------------------------------------------------------------ 4. volumes par zone
def size(path):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs)


for z in ("bronze", "silver", "gold"):
    log(f"  volume {z:<6} : {size(os.path.join(LAKE, z)) / 1e6:8.1f} Mo")
b = size(os.path.join(LAKE, "bronze", "tpcxbb", "store_sales"))
sv = size(silver_dir)
log(f"  store_sales : texte {b / 1e6:.1f} Mo -> Parquet {sv / 1e6:.1f} Mo (÷{b / sv:.1f})")
