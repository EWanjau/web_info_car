import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

CSV_FILE = "car_data.csv"

# conection to Aiven
def get_connection():
    return psycopg2.connect(
        host=os.getenv("AIVEN_HOST"),
        port=os.getenv("AIVEN_PORT"),
        dbname=os.getenv("AIVEN_DB"),
        user=os.getenv("AIVEN_USER"),
        password=os.getenv("AIVEN_PASSWORD")
    )

# create table if not exists
def create_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cars (
                ref_id            VARCHAR(20) PRIMARY KEY,
                name              TEXT,
                chassis_code      VARCHAR(50),
                year              SMALLINT,
                price_usd         VARCHAR(20),
                price_jpy         BIGINT,
                mileage_km        INTEGER,
                engine_cc         INTEGER,
                fuel              VARCHAR(20),
                transmission      VARCHAR(20),
                steering          VARCHAR(30),
                vehicle_type      VARCHAR(30),
                options           TEXT,
                has_sunroof       SMALLINT,
                has_leather       SMALLINT,
                has_navigation    SMALLINT,
                has_alloy_wheels  SMALLINT,
                has_4wd           SMALLINT,
                has_airbag        SMALLINT,
                has_abs           SMALLINT,
                has_camera        SMALLINT,
                location          TEXT,
                date_listed       VARCHAR(30),
                detail_url        TEXT,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    print("Table ready.")

# load the csv and insert into DB
def load_csv(conn):
    # Check CSV exists
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found in current directory.")
        return

    print(f"Reading {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)
    print(f"Total rows in CSV: {len(df)}")

    # Drop duplicates within the CSV itself
    df.drop_duplicates(subset="ref_id", inplace=True)
    print(f"After deduplication: {len(df)} rows")

    # Clean numeric columns
    for col in ["year", "price_jpy", "mileage_km", "engine_cc"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    inserted = 0
    skipped  = 0
    errors   = 0

    with conn.cursor() as cur:
        for _, row in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO cars (
                        ref_id, name, chassis_code, year, price_usd, price_jpy,
                        mileage_km, engine_cc, fuel, transmission, steering,
                        vehicle_type, options, has_sunroof, has_leather,
                        has_navigation, has_alloy_wheels, has_4wd, has_airbag,
                        has_abs, has_camera, location, date_listed, detail_url
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (ref_id) DO NOTHING;
                """, (
                    row["ref_id"], row["name"], row["chassis_code"],
                    None if pd.isna(row["year"])       else int(row["year"]),
                    row["price_usd"],
                    None if pd.isna(row["price_jpy"])  else int(row["price_jpy"]),
                    None if pd.isna(row["mileage_km"]) else int(row["mileage_km"]),
                    None if pd.isna(row["engine_cc"])  else int(row["engine_cc"]),
                    row["fuel"], row["transmission"], row["steering"],
                    row["vehicle_type"], row["options"],
                    row["has_sunroof"], row["has_leather"], row["has_navigation"],
                    row["has_alloy_wheels"], row["has_4wd"], row["has_airbag"],
                    row["has_abs"], row["has_camera"],
                    row["location"], row["date_listed"], row["detail_url"]
                ))

                # Check if row was actually inserted or skipped
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1

            except Exception as e:
                print(f"  [!] Error on ref_id {row['ref_id']}: {e}")
                conn.rollback()
                errors += 1
                continue

        conn.commit()

    print(f"\nDone!")
    print(f"  Inserted : {inserted}")
    print(f"  Skipped  : {skipped} (already in DB)")
    print(f"  Errors   : {errors}")


# main
def main():
    print("Connecting to Aiven...")
    conn = get_connection()
    create_table(conn)
    load_csv(conn)
    conn.close()


if __name__ == "__main__":
    main()