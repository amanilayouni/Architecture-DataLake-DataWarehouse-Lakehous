# -*- coding: utf-8 -*-
"""Jour 4 - UC-08 : analyses KPI, statistiques descriptives et visualisations.

Lit les jeux Silver et Gold produits au Jour 3 (env. J3_OUT_DIR,
defaut /home/amani/j3_data dans la VM) et produit :
  - les KPI du dictionnaire UC-01 calculables sur ces jeux (K01, K03, K04, K05, K07, K08)
  - des statistiques descriptives sur store_sales
  - deux analyses metier : evolution mensuelle du CA, comparaison des magasins
    (+ CA par categorie de produit en complement)
  - des visualisations PNG et des exports CSV

Sorties : J4_OUT_DIR (defaut /home/amani/j4_data)
  outputs/        CSV de resultats (kpi.csv, stats_descriptives.csv, ...)
  visualisations/ PNG des graphiques
"""
import os
import sys

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
import matplotlib
matplotlib.use("Agg")  # pas d'affichage dans la VM

J3 = os.environ.get("J3_OUT_DIR", "/home/amani/j3_data")
J4 = os.environ.get("J4_OUT_DIR", "/home/amani/j4_data")
OUT = os.path.join(J4, "outputs")
VIS = os.path.join(J4, "visualisations")
for d in (OUT, VIS):
    os.makedirs(d, exist_ok=True)

from pyspark.sql import SparkSession, functions as F  # noqa: E402

SILVER = os.path.join(J3, "silver")
GOLD = os.path.join(J3, "gold", "ventes_mensuelles_magasin")


def main():
    spark = (SparkSession.builder.appName("TP4-analyses")
             .master("local[2]").getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    print("=== UC-08 : analyses sur les jeux Silver / Gold du Jour 3 ===")
    print("lecture silver :", SILVER)
    print("lecture gold   :", GOLD)

    ventes = spark.read.parquet(os.path.join(SILVER, "store_sales"))
    item = spark.read.parquet(os.path.join(SILVER, "item"))
    mag = spark.read.parquet(os.path.join(SILVER, "store"))
    dates = spark.read.parquet(os.path.join(SILVER, "date_dim"))
    gold = spark.read.parquet(GOLD)

    # ---------------- verification des jeux selectionnes ----------------
    print("\n## jeux selectionnes")
    for nom, df in [("silver/store_sales", ventes), ("silver/item", item),
                    ("silver/store", mag), ("silver/date_dim", dates),
                    ("gold/ventes_mensuelles_magasin", gold)]:
        print("{0:35} {1:>7} lignes, {2} colonnes".format(nom, df.count(), len(df.columns)))

    # ---------------- KPI (dictionnaire UC-01) ----------------
    print("\n## KPI calcules (dictionnaire UC-01)")
    agg = ventes.agg(
        F.round(F.sum("ss_net_paid"), 2).alias("k01_ca_net"),
        F.countDistinct("ss_ticket_number").alias("k03_transactions"),
        F.round(F.sum("ss_quantity"), 0).alias("k05_quantites"),
        F.round(F.sum("ss_ext_discount_amt"), 2).alias("remise_totale"),
        F.round(F.sum("ss_ext_list_price"), 2).alias("prix_catalogue_total"),
        F.round(F.sum("ss_net_profit"), 2).alias("k08_marge_nette"),
        F.round(F.sum("ss_ext_sales_price"), 2).alias("ca_brut"),
        F.count("*").alias("lignes_vente"),
    ).first()

    k01 = float(agg["k01_ca_net"]); k03 = int(agg["k03_transactions"])
    k04 = round(k01 / k03, 2); k05 = int(agg["k05_quantites"])
    k07 = round(100.0 * agg["remise_totale"] / agg["prix_catalogue_total"], 2)
    k08 = float(agg["k08_marge_nette"])
    k08_taux = round(100.0 * k08 / k01, 2)

    lignes_kpi = [
        ("K01", "Chiffre d'affaires net magasin", "SUM(ss_net_paid)",
         k01, "$", "2001-2005, 12 magasins"),
        ("K03", "Nombre de transactions", "COUNT(DISTINCT ss_ticket_number)",
         k03, "tickets", "2001-2005"),
        ("K04", "Panier moyen", "K01 / K03", k04, "$/transaction", "2001-2005"),
        ("K05", "Quantites vendues", "SUM(ss_quantity)", k05, "unites", "2001-2005"),
        ("K07", "Taux de remise", "SUM(ss_ext_discount_amt)/SUM(ss_ext_list_price)*100",
         k07, "%", "2001-2005"),
        ("K08", "Marge nette", "SUM(ss_net_profit)", k08, "$", "2001-2005"),
        ("K08b", "Taux de marge", "K08 / K01 * 100", k08_taux, "%", "2001-2005"),
    ]
    for r in lignes_kpi:
        print("{0:4} {1:35} = {2} {3}".format(r[0], r[1], r[3], r[4]))
    import pandas as pd
    pd.DataFrame(lignes_kpi, columns=[
        "id", "nom", "formule", "valeur", "unite", "perimetre"]).to_csv(
        os.path.join(OUT, "kpi.csv"), index=False)

    # comparaison avec les valeurs de test UC-01 (annuelles)
    print("\n## verification : CA net par annee vs dictionnaire UC-01")
    ca_annee = (ventes.join(dates.select("d_date_sk", "d_year"),
                            ventes["ss_sold_date_sk"] == dates["d_date_sk"], "left")
                .groupBy("d_year")
                .agg(F.round(F.sum("ss_net_paid"), 2).alias("ca_net"),
                     F.countDistinct("ss_ticket_number").alias("transactions"))
                .orderBy("d_year"))
    ca_annee.show()
    ca_annee.toPandas().to_csv(os.path.join(OUT, "ca_par_annee.csv"), index=False)

    # ---------------- statistiques descriptives ----------------
    print("\n## statistiques descriptives - silver/store_sales")
    stats = (ventes.select(
        F.count("*").alias("nb_lignes"),
        F.min("ss_net_paid").alias("net_paid_min"),
        F.round(F.max("ss_net_paid"), 2).alias("net_paid_max"),
        F.round(F.mean("ss_net_paid"), 2).alias("net_paid_moyenne"),
        F.round(F.expr("percentile_approx(ss_net_paid, 0.5)"), 2).alias("net_paid_mediane"),
        F.min("ss_quantity").alias("quantite_min"),
        F.max("ss_quantity").alias("quantite_max"),
        F.round(F.mean("ss_quantity"), 2).alias("quantite_moyenne"),
        F.countDistinct("ss_item_sk").alias("articles_distincts"),
        F.countDistinct("ss_store_sk").alias("magasins_distincts"),
        F.countDistinct("ss_customer_sk").alias("clients_distincts"),
    ).first())
    for k, v in stats.asDict().items():
        print("{0:22} {1}".format(k, v))
    pd.DataFrame([stats.asDict()]).to_csv(
        os.path.join(OUT, "stats_descriptives.csv"), index=False)

    # periode couverte
    per = (ventes.join(dates.select("d_date_sk", "d_date"),
                       ventes["ss_sold_date_sk"] == dates["d_date_sk"], "left")
           .agg(F.min("d_date"), F.max("d_date")).first())
    print("periode couverte :", per[0], "->", per[1])

    # ---------------- analyse 1 : evolution mensuelle ----------------
    print("\n## analyse 1 : evolution du CA net par mois (jeu Gold)")
    mensuel = (gold.groupBy("d_year", "d_moy")
               .agg(F.round(F.sum("ca_net"), 2).alias("ca_net"),
                    F.sum("quantite_vendue").alias("quantites"))
               .orderBy("d_year", "d_moy"))
    pdf_m = mensuel.toPandas()
    pdf_m["mois"] = pdf_m["d_year"].astype(str) + "-" + pdf_m["d_moy"].astype(str).str.zfill(2)
    pdf_m.to_csv(os.path.join(OUT, "ca_mensuel.csv"), index=False)
    print(pdf_m.head(6).to_string(index=False))
    print("meilleur mois :", pdf_m.loc[pdf_m["ca_net"].idxmax(), ["mois", "ca_net"]].tolist())
    print("moins bon mois :", pdf_m.loc[pdf_m["ca_net"].idxmin(), ["mois", "ca_net"]].tolist())
    top = pdf_m.nlargest(12, "ca_net")["mois"].str[-2:].value_counts()
    print("repartition des 12 meilleurs mois par mois civil :", dict(top))

    import matplotlib.pyplot as plt
    plt.figure(figsize=(12, 5))
    plt.plot(pdf_m["mois"], pdf_m["ca_net"], marker="o", markersize=3)
    plt.title("Evolution du chiffre d'affaires net magasin par mois (2001-2005)")
    plt.xlabel("Mois")
    plt.ylabel("CA net ($)")
    pas = list(range(0, len(pdf_m), 6))
    plt.xticks(pas, pdf_m["mois"].iloc[pas], rotation=45)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(VIS, "visualisation_2_evolution_ca_mensuel.png"),
                dpi=150, bbox_inches="tight")
    plt.close()

    # ---------------- analyse 2 : comparaison des magasins ----------------
    print("\n## analyse 2 : comparaison des 12 magasins")
    par_mag = (gold.groupBy("s_store_sk", "s_store_name")
               .agg(F.round(F.sum("ca_net"), 2).alias("ca_net"),
                    F.sum("quantite_vendue").alias("quantites"),
                    F.round(F.sum("marge_nette"), 2).alias("marge"))
               .orderBy(F.desc("ca_net")))
    pdf_s = par_mag.toPandas()
    trans_mag = (ventes.groupBy("ss_store_sk")
                 .agg(F.countDistinct("ss_ticket_number").alias("transactions")))
    pdf_t = trans_mag.toPandas().rename(columns={"ss_store_sk": "s_store_sk"})
    pdf_s = pdf_s.merge(pdf_t, on="s_store_sk")
    pdf_s["panier_moyen"] = (pdf_s["ca_net"] / pdf_s["transactions"]).round(2)
    pdf_s.to_csv(os.path.join(OUT, "ca_par_magasin.csv"), index=False)
    print(pdf_s.to_string(index=False))
    ecart = round(100.0 * (pdf_s["ca_net"].max() - pdf_s["ca_net"].min())
                  / pdf_s["ca_net"].mean(), 2)
    print("ecart max/min vs moyenne : {0} %".format(ecart))

    plt.figure(figsize=(11, 5))
    plt.bar(pdf_s["s_store_name"], pdf_s["ca_net"] / 1e6, color="#4472A8")
    plt.title("Chiffre d'affaires net par magasin (total 2001-2005)")
    plt.xlabel("Magasin")
    plt.ylabel("CA net (millions $)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(VIS, "visualisation_1_ca_par_magasin.png"),
                dpi=150, bbox_inches="tight")
    plt.close()

    # ---------------- analyse 3 : CA par categorie de produit ----------------
    print("\n## analyse 3 : CA net par categorie de produit (complement)")
    par_cat = (ventes.join(item.select("i_item_sk", "i_category"),
                           ventes["ss_item_sk"] == item["i_item_sk"], "left")
               .groupBy("i_category")
               .agg(F.round(F.sum("ss_net_paid"), 2).alias("ca_net"),
                    F.sum("ss_quantity").alias("quantites"))
               .orderBy(F.desc("ca_net")))
    pdf_c = par_cat.toPandas()
    pdf_c.to_csv(os.path.join(OUT, "ca_par_categorie.csv"), index=False)
    print(pdf_c.to_string(index=False))

    plt.figure(figsize=(11, 5))
    plt.bar(pdf_c["i_category"], pdf_c["ca_net"] / 1e6, color="#5B8C5A")
    plt.title("Chiffre d'affaires net par categorie de produit (2001-2005)")
    plt.xlabel("Categorie")
    plt.ylabel("CA net (millions $)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(VIS, "visualisation_3_ca_par_categorie.png"),
                dpi=150, bbox_inches="tight")
    plt.close()

    print("\nfichiers produits :")
    for d in (OUT, VIS):
        for f in sorted(os.listdir(d)):
            print("  ", os.path.join(d, f))
    spark.stop()
    print("TERMINE")


if __name__ == "__main__":
    main()
