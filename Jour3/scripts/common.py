# -*- coding: utf-8 -*-
"""Elements communs aux traitements du Jour 3 : session Spark, chemins, schemas."""
import os
import sys

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)

# --- chemins (modifiables par variables d'environnement) ---
# J3_RAW_MODE=hdfs : lecture dans la zone Raw du data lake (Jour 2)
# sinon : lecture locale des copies .dat du kit
RAW_MODE = os.environ.get("J3_RAW_MODE", "local")
RAW_DIR = os.environ.get(
    "J3_RAW_DIR",
    r"C:\Users\msi\Downloads\retail_project\retail_project\data")
if RAW_MODE == "hdfs":
    HDFS = "hdfs://localhost:9000"
    SOURCES = {
        "store_sales": HDFS + "/retail-lake/raw/tpcxbb/initial/store_sales.dat",
        "item":        HDFS + "/retail-lake/raw/tpcxbb/initial/item.dat",
        "date_dim":    HDFS + "/retail-lake/raw/tpcxbb/initial/date_dim.dat",
        # store.dat a ete depose par le flux NiFi du Jour 2
        "store":       HDFS + "/retail-lake/raw/nifi/store.dat",
    }
else:
    SOURCES = {t: os.path.join(RAW_DIR, t, t + ".dat")
               for t in ["store_sales", "item", "store", "date_dim"]}
J3_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# J3_OUT_DIR : dossier parent des zones de sortie (dans la VM : /home/amani/j3_data)
OUT_DIR = os.environ.get("J3_OUT_DIR", J3_DIR)
SILVER_DIR = os.path.join(OUT_DIR, "silver")
GOLD_DIR = os.path.join(OUT_DIR, "gold")
PARQUET_DIR = os.path.join(OUT_DIR, "parquet")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tpcxbb_schema import SCHEMA  # noqa: E402

from pyspark.sql import SparkSession, types as T  # noqa: E402

# Types explicites par table (le suffixe _sk ne suffit pas :
# i_item_id, d_date_id et s_store_id sont des chaines dans les fichiers)
COL_TYPES = {
    "store_sales": {
        "ss_sold_date_sk": "long", "ss_sold_time_sk": "long",
        "ss_item_sk": "long", "ss_customer_sk": "long",
        "ss_cdemo_sk": "long", "ss_hdemo_sk": "long",
        "ss_addr_sk": "long", "ss_store_sk": "long",
        "ss_promo_sk": "long", "ss_ticket_number": "long",
        "ss_quantity": "int",
        "ss_wholesale_cost": "double", "ss_list_price": "double",
        "ss_sales_price": "double", "ss_ext_discount_amt": "double",
        "ss_ext_sales_price": "double", "ss_ext_wholesale_cost": "double",
        "ss_ext_list_price": "double", "ss_ext_tax": "double",
        "ss_coupon_amt": "double", "ss_net_paid": "double",
        "ss_net_paid_inc_tax": "double", "ss_net_profit": "double",
    },
    "item": {
        "i_item_sk": "long", "i_item_id": "string",
        "i_rec_start_date": "string", "i_rec_end_date": "string",
        "i_item_desc": "string", "i_current_price": "double",
        "i_wholesale_cost": "double", "i_brand_id": "long",
        "i_brand": "string", "i_class_id": "long", "i_class": "string",
        "i_category_id": "long", "i_category": "string",
        "i_manufact_id": "long", "i_manufact": "string",
        "i_size": "string", "i_formulation": "string",
        "i_color": "string", "i_units": "string",
        "i_container": "string", "i_manager_id": "long",
        "i_product_name": "string",
    },
    "store": {
        "s_store_sk": "long", "s_store_id": "string",
        "s_rec_start_date": "string", "s_rec_end_date": "string",
        "s_closed_date_sk": "long", "s_store_name": "string",
        "s_number_employees": "int", "s_floor_space": "int",
        "s_hours": "string", "s_manager": "string",
        "s_market_id": "long", "s_geography_class": "string",
        "s_market_desc": "string", "s_market_manager": "string",
        "s_division_id": "long", "s_division_name": "string",
        "s_company_id": "long", "s_company_name": "string",
        "s_street_number": "string", "s_street_name": "string",
        "s_street_type": "string", "s_suite_number": "string",
        "s_city": "string", "s_county": "string", "s_state": "string",
        "s_zip": "string", "s_country": "string",
        "s_gmt_offset": "double", "s_tax_precentage": "double",
    },
    "date_dim": {
        "d_date_sk": "long", "d_date_id": "string", "d_date": "date",
        "d_month_seq": "long", "d_week_seq": "long",
        "d_quarter_seq": "long", "d_year": "long", "d_dow": "long",
        "d_moy": "long", "d_dom": "long", "d_qoy": "long",
        "d_fy_year": "long", "d_fy_quarter_seq": "long",
        "d_fy_week_seq": "long", "d_day_name": "string",
        "d_quarter_name": "string", "d_holiday": "string",
        "d_weekend": "string", "d_following_holiday": "string",
        "d_first_dom": "long", "d_last_dom": "long",
        "d_same_day_ly": "long", "d_same_day_lq": "long",
        "d_current_day": "string", "d_current_week": "string",
        "d_current_month": "string", "d_current_quarter": "string",
        "d_current_year": "string",
    },
}


def spark_session(name="Jour3"):
    spark = (SparkSession.builder
             .appName(name)
             .master("local[2]")
             .config("spark.driver.memory", "1g")
             .config("spark.ui.enabled", "false")
             .config("spark.sql.shuffle.partitions", "8")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")
    return spark


def schema_of(table):
    mapping = {"long": T.LongType(), "int": T.IntegerType(),
               "double": T.DoubleType(), "date": T.DateType(),
               "string": T.StringType()}
    return T.StructType([
        T.StructField(c, mapping[COL_TYPES[table][c]], True)
        for c in SCHEMA[table]
    ])


def lire(spark, table):
    """Lit un fichier .dat (separateur |, pas d'en-tete, fin de ligne |)."""
    return (spark.read
            .option("sep", "|")
            .option("mode", "PERMISSIVE")
            .schema(schema_of(table))
            .csv(SOURCES[table]))
