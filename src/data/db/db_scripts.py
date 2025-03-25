import csv
import os
from pathlib import Path
import sqlite3
import sys

from dotenv import load_dotenv

from src.misc.path_parser import get_db_path

cwd = os.getcwd()
sys.path.insert(0, "f{cwd}/src")

load_dotenv()


def csv_to_sqlite(csv_file_path, sqlite_db_path, table_name):
    """
    Converts a CSV file into a SQLite database table.

    :param csv_file_path: Path to the input CSV file.
    :param sqlite_db_path: Path to the output SQLite database file.
    :param table_name: Name of the table to create in the database.
    """

    # Delete the SQLite database file if it exists
    if os.path.exists(sqlite_db_path):
        os.remove(sqlite_db_path)

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()

    # Open the CSV file
    with open(csv_file_path, "r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)

        # Extract the header (first row)
        headers = next(reader)

        # Create table with columns based on the header
        columns = ", ".join([f'"{header}" TEXT' for header in headers])
        create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns});"
        cursor.execute(create_table_query)

        # Insert data into the table
        insert_query = f'INSERT INTO {table_name} ({", ".join(headers)}) VALUES ({", ".join(["?" for _ in headers])});'
        for row in reader:
            cursor.execute(insert_query, row)

    # Commit changes and close the connection
    conn.commit()
    conn.close()

    print(
        f"CSV data has been successfully imported into the table '{table_name}' in '{sqlite_db_path}'."
    )


def query_sqlite_db(sqlite_db_path, query, throw=False):
    """
    Queries a SQLite database and prints the results.

    :param sqlite_db_path: Path to the SQLite database file.
    :param query: SQL query to execute.
    """
    if not os.path.exists(sqlite_db_path):
        print(f"Database file '{sqlite_db_path}' does not exist.")
        return

    # Connect to SQLite database
    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()

    data = []
    try:
        # Execute the query
        cursor.execute(query)
        rows = cursor.fetchall()
        data.extend(rows)
    except sqlite3.Error as e:
        if throw:
            raise sqlite3.Error(e)
        print(f"An error has occured: {e}")
    finally:
        # Close the connection
        conn.close()
    return data


def set_db(reset=False):
    """
    Reset db to the initial state
    """
    synthetic_data_path = f"{cwd}/dataset"
    sqlite_path = get_db_path()

    sql_builder = [
        {
            "csv_file_path": f"{synthetic_data_path}/emails.csv",
            "sqlite_db_path": f"{sqlite_path}/emails.db",
            "table_name": "emails",
        },
        {
            "csv_file_path": f"{synthetic_data_path}/transactions.csv",
            "sqlite_db_path": f"{sqlite_path}/transactions.db",
            "table_name": "transactions",
        },
    ]

    if not os.path.exists(sqlite_path):
        os.makedirs(sqlite_path)

    for x in sql_builder:
        db_exists = Path(x["sqlite_db_path"]).is_file()
        csv_exists = Path(x["csv_file_path"]).is_file()

        if ((not reset) & db_exists) | (not csv_exists):
            continue

        csv_to_sqlite(**x)
