# -*- coding: utf-8 -*-
"""Jour 3 - transformations : silver -> gold + enregistrement Parquet.

Jeu Gold : ventes_mensuelles_magasin
  Question metier (Jour 1) : suivre le CA net par magasin et par periode.
  Granularite : magasin x annee x mois.
  Jointures verifiees au Jour 1 (0 orphelin) :
    ss_sold_date_sk -> d_date_sk, ss_store_sk -> s_store_sk.
  Les lignes sans date de vente (ss_sold_date_sk null) sont conservees
  dans Silver mais exclues de cette synthese mensuelle (trace au rapport).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import GOLD_DIR, PARQUET_DIR, SILVER_DIR, spark_session  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402


def main():
    spark = spark_session("Jour3-transformations")
    print("=== TRANSFORMATIONS silver -> gold ===")

    ventes = spark.read.parquet(os.path.join(SILVER_DIR, "store_sales"))
    dates = spark.read.parquet(os.path.join(SILVER_DIR, "date_dim"))
    mag = spark.read.parquet(os.path.join(SILVER_DIR, "store"))
    print("silver store_sales :", ventes.count(), "| date_dim :",
          dates.count(), "| store :", mag.count())

    sans_date = ventes.filter(F.col("ss_sold_date_sk").isNull()).count()
    print("lignes ventes sans date (conservees en silver, exclues du gold) :",
          sans_date)

    # --- jointure verifiee : ventes -> date_dim -> store ---
    v = ventes.filter(F.col("ss_sold_date_sk").isNotNull())
    nb_avant = v.count()
    vd = v.join(dates.select("d_date_sk", "d_year", "d_moy", "d_quarter_name"),
                v["ss_sold_date_sk"] == dates["d_date_sk"], "left")
    orphelins_d = vd.filter(F.col("d_date_sk").isNull()).count()
    vdm = vd.join(mag.select("s_store_sk", "s_store_name"),
                  vd["ss_store_sk"] == mag["s_store_sk"], "left")
    orphelins_s = vdm.filter(F.col("s_store_sk").isNull()).count()
    nb_apres = vdm.count()
    print("jointure ventes->date_dim : orphelins =", orphelins_d)
    print("jointure ventes->store    : orphelins =", orphelins_s)
    print("lignes avant jointure :", nb_avant, "| apres :", nb_apres)

    # --- agregation metier ---
    gold = (vdm.groupBy("s_store_sk", "s_store_name", "d_year", "d_moy")
               .agg(F.round(F.sum("ss_net_paid"), 2).alias("ca_net"),
                    F.sum("ss_quantity").alias("quantite_vendue"),
                    F.count("*").alias("nb_lignes_vente"),
                    F.round(F.sum("ss_net_profit"), 2).alias("marge_nette"))
               .orderBy("d_year", "d_moy", "s_store_sk"))
    print("\n### jeu gold : ventes_mensuelles_magasin")
    gold.printSchema()
    gold.show(15, truncate=False)
    print("lignes gold :", gold.count())

    dest = os.path.join(GOLD_DIR, "ventes_mensuelles_magasin")
    gold.write.mode("overwrite").parquet(dest)
    print("gold ecrit dans :", dest)

    # --- Parquet : ecriture + relecture + comparaison de formats ---
    print("\n### Parquet : ecriture et relecture")
    relu = spark.read.parquet(dest)
    relu.printSchema()
    print("lignes relues :", relu.count())

    print("\n### comparaison des formats (meme jeu gold)")
    csv_d = os.path.join(PARQUET_DIR, "gold_csv")
    json_d = os.path.join(PARQUET_DIR, "gold_json")
    gold.coalesce(1).write.mode("overwrite").option("header", True).csv(csv_d)
    gold.coalesce(1).write.mode("overwrite").json(json_d)
    relu_csv = spark.read.option("header", True).csv(csv_d)
    relu_json = spark.read.json(json_d)
    print("relecture csv :", relu_csv.count(), "lignes | relecture json :",
          relu_json.count(), "lignes | parquet :", relu.count())

    for nom, d in [("csv", csv_d), ("json", json_d), ("parquet", dest)]:
        taille = sum(os.path.getsize(os.path.join(dp, f))
                     for dp, _, fs in os.walk(d) for f in fs
                     if not f.startswith("_") and not f.startswith("."))
        print("taille", nom.ljust(8), ":", taille, "octets")

    spark.stop()
    print("\nTERMINE")


if __name__ == "__main__":
    main()
