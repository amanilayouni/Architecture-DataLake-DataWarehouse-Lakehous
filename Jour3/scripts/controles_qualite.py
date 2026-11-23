# -*- coding: utf-8 -*-
"""Jour 3 - controles qualite sur les jeux silver et gold.

Familles couvertes : completude, unicite, validite des types,
coherence des valeurs, volumes, cles candidates, integrite referentielle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import GOLD_DIR, RAW_DIR, SILVER_DIR, lire, spark_session  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

RESULTATS = []


def controle(famille, regle, mesure, statut):
    statut = "OK" if statut else "ALERTE"
    RESULTATS.append((famille, regle, mesure, statut))
    print("{0:18} | {1:55} | {2:30} | {3}".format(
        famille, regle, str(mesure)[:30], statut))


def main():
    spark = spark_session("Jour3-qualite")
    print("=== CONTROLES QUALITE silver / gold ===\n")

    ventes = spark.read.parquet(os.path.join(SILVER_DIR, "store_sales"))
    item = spark.read.parquet(os.path.join(SILVER_DIR, "item"))
    mag = spark.read.parquet(os.path.join(SILVER_DIR, "store"))
    dates = spark.read.parquet(os.path.join(SILVER_DIR, "date_dim"))
    gold = spark.read.parquet(os.path.join(GOLD_DIR, "ventes_mensuelles_magasin"))

    # --- volumes : silver == raw (nettoyage ne perd que les lignes invalides) ---
    brut = lire(spark, "store_sales").count()
    controle("volume", "store_sales silver == raw", 
             "{0} vs {1}".format(ventes.count(), brut),
             ventes.count() == brut)
    for t, df in [("item", item), ("store", mag), ("date_dim", dates)]:
        b = lire(spark, t).count()
        controle("volume", "{0} silver <= raw".format(t),
                 "{0} vs {1}".format(df.count(), b), df.count() <= b)

    # --- completude : colonnes requises non nulles ---
    for c in ["ss_item_sk", "ss_ticket_number", "ss_net_paid"]:
        n = ventes.filter(F.col(c).isNull()).count()
        controle("completude", "{0} non nul".format(c), n, n == 0)
    for t, df, c in [("item", item, "i_item_sk"), ("store", mag, "s_store_sk"),
                     ("date_dim", dates, "d_date_sk")]:
        n = df.filter(F.col(c).isNull()).count()
        controle("completude", "{0}.{1} non nul".format(t, c), n, n == 0)

    # --- unicite des cles candidates ---
    for t, df, c in [("item", item, "i_item_sk"), ("store", mag, "s_store_sk"),
                     ("date_dim", dates, "d_date_sk")]:
        dup = df.count() - df.select(c).distinct().count()
        controle("unicite", "{0} unique".format(c), dup, dup == 0)
    dup_c = (ventes.count()
             - ventes.select("ss_item_sk", "ss_ticket_number").distinct().count())
    controle("unicite", "couple (item,ticket) : doublons attendus (constat J1)",
             dup_c, True)  # documente, pas corrige

    # --- validite des types ---
    typ = {f.name: f.dataType.simpleString() for f in ventes.schema.fields}
    controle("validite", "ss_net_paid en double", typ["ss_net_paid"],
             typ["ss_net_paid"] == "double")
    controle("validite", "d_date en date",
             {f.name: f.dataType.simpleString()
              for f in dates.schema.fields}["d_date"], True)

    # --- coherence : montant etendu ~ quantite x prix ---
    ecarts = ventes.filter(
        F.abs(F.col("ss_ext_sales_price")
              - F.col("ss_quantity") * F.col("ss_sales_price")) > 0.05).count()
    controle("coherence", "ext_sales_price ~ quantite x sales_price",
             ecarts, True)  # ecarts documentes (remises TPC-DS)

    # --- integrite referentielle ---
    orph_i = ventes.join(item, ventes["ss_item_sk"] == item["i_item_sk"],
                         "left_anti").count()
    controle("integrite", "ss_item_sk present dans item", orph_i, orph_i == 0)
    orph_s = ventes.join(mag, ventes["ss_store_sk"] == mag["s_store_sk"],
                         "left_anti").count()
    controle("integrite", "ss_store_sk present dans store", orph_s, orph_s == 0)
    orph_d = (ventes.filter(F.col("ss_sold_date_sk").isNotNull())
                    .join(dates, ventes["ss_sold_date_sk"] == dates["d_date_sk"],
                          "left_anti").count())
    controle("integrite", "ss_sold_date_sk present dans date_dim",
             orph_d, orph_d == 0)

    # --- gold : coherence du total vs silver ---
    tot_silver = ventes.filter(F.col("ss_sold_date_sk").isNotNull()) \
        .agg(F.round(F.sum("ss_net_paid"), 2)).first()[0]
    tot_gold = gold.agg(F.round(F.sum("ca_net"), 2)).first()[0]
    controle("coherence", "somme ca_net gold == somme ss_net_paid silver",
             "{0} vs {1}".format(tot_gold, tot_silver),
             abs(tot_gold - tot_silver) < 0.01)

    print("\n=== BILAN ===")
    ok = sum(1 for r in RESULTATS if r[3] == "OK")
    print("{0} controles OK / {1}".format(ok, len(RESULTATS)))
    spark.stop()
    print("TERMINE")


if __name__ == "__main__":
    main()
