# -*- coding: utf-8 -*-
"""Jour 3 - nettoyage : raw (.dat) -> silver (parquet) pour les 4 sources.

Regles appliquees (justifiees dans UC06_traitements_PySpark.pdf) :
  R1 cast explicite des types (les .dat n'ont ni en-tete ni types)
  R2 trim des colonnes texte
  R3 conversion des dates texte en type date
  R4 colonnes requises non nulles (cles) -> lignes invalides mises a l'ecart
  R5 doublons de cle candidate supprimes UNIQUEMENT pour les dimensions
     (store_sales garde ses doublons de cle composite : un meme article peut
     figurer plusieurs fois sur un ticket, constat Jour 1)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW_MODE, SILVER_DIR, SOURCES, lire, spark_session  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

REQUISES = {
    "store_sales": ["ss_item_sk", "ss_ticket_number", "ss_net_paid"],
    "item":        ["i_item_sk"],
    "store":       ["s_store_sk"],
    "date_dim":    ["d_date_sk", "d_date"],
}
DATES_TEXTE = {
    "item":  ["i_rec_start_date", "i_rec_end_date"],
    "store": ["s_rec_start_date", "s_rec_end_date"],
}
CLE_UNICITE = {"item": "i_item_sk", "store": "s_store_sk", "date_dim": "d_date_sk"}

TABLES = ["item", "store", "date_dim", "store_sales"]


def nettoyer(df, table):
    d = df
    # R2 : trim des chaines
    for f in d.schema.fields:
        if f.dataType.simpleString() == "string":
            d = d.withColumn(f.name, F.trim(F.col(f.name)))
    # R3 : dates texte -> date
    for c in DATES_TEXTE.get(table, []):
        d = d.withColumn(c, F.to_date(F.col(c), "yyyy-MM-dd"))
    # R4 : ecart des lignes sans cle requise
    nb_avant = d.count()
    cond = None
    for c in REQUISES[table]:
        cond = F.col(c).isNotNull() if cond is None else cond & F.col(c).isNotNull()
    valides = d.filter(cond)
    ecart = d.filter(~cond)
    nb_ecart = ecart.count()
    # R5 : dedoublonnage sur cle candidate des dimensions
    dedup = 0
    cle = CLE_UNICITE.get(table)
    if cle:
        nb_u = valides.select(cle).distinct().count()
        tot = valides.count()
        if nb_u < tot:
            valides = valides.dropDuplicates([cle])
        dedup = tot - valides.count()
    return valides, ecart, nb_avant, nb_ecart, dedup


def main():
    spark = spark_session("Jour3-nettoyage")
    print("=== NETTOYAGE raw -> silver ===")
    print("mode de lecture :", RAW_MODE)
    for t, p in SOURCES.items():
        print("  ", t.ljust(12), p)
    for table in TABLES:
        print("\n#### ", table)
        brut = lire(spark, table)
        print("schema lu (types explicites) :")
        brut.printSchema()
        valides, ecart, nb_avant, nb_ecart, dedup = nettoyer(brut, table)
        print("lignes lues        :", nb_avant)
        print("mises a l'ecart  :", nb_ecart, "(cle requise nulle)")
        print("doublons retires :", dedup)
        print("lignes conservees:", valides.count())
        if nb_ecart:
            ecart.show(3, truncate=40)
        dest = os.path.join(SILVER_DIR, table)
        valides.write.mode("overwrite").parquet(dest)
        print("silver ecrit dans:", dest)
        relu = spark.read.parquet(dest)
        print("relecture parquet:", relu.count(), "lignes,", len(relu.columns), "colonnes")
    spark.stop()
    print("\nTERMINE")


if __name__ == "__main__":
    main()
