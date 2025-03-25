import json
from sys import argv
import pandas as pd
import sqlite3

db_filepath = argv[1]

print(f"Purging database {db_filepath}...")


# Connect to SQLite database
conn = sqlite3.connect(db_filepath)

query = "SELECT * FROM emails"

df = pd.read_sql(query, conn)

if "full_logs" in df.columns:
    json_file = db_filepath.replace("emails.db", "full_logs.json")

    last_completed = df[df["full_logs"] != ""].iloc[-1]
    full_logs = json.loads(last_completed["full_logs"])
    json.dump(full_logs, open(json_file, "w"), indent=4)
    print("full_logs saved to", json_file)
    print(f"full logs len {len(full_logs)}")

    conn.execute("ALTER TABLE emails DROP COLUMN full_logs")
    conn.execute("VACUUM")
    conn.commit()
    print("Purged database:", db_filepath)
else:
    print(f"No need to purge database:", db_filepath)

# Close the connection
conn.close()
