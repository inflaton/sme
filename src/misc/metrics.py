import sqlite3
import pandas as pd
import matplotlib.pyplot as plt


def plot_value_distribution(df2, col="category", top_n=10):
    df2[col].value_counts()[:top_n].plot(kind="bar")
    plt.title(f"Distribution of {col}")

    # add the count on top of the bars
    for i in range(len(df2[col].value_counts()[:top_n])):
        count = df2[col].value_counts().values[i]
        plt.text(i, count, count, ha="center")

    plt.show()


def get_email_id_associated_with_duplicated_invoice_id(debug=False):
    transactions_df = pd.read_csv("./src/data/synthetic_data/transactions.csv")
    ground_truth_df = pd.read_csv("./ground_truth_data 2.csv")

    num_duplicates = transactions_df["invoice_id"].duplicated(keep=False).sum()
    if debug:
        print(f"Number of duplicate invoice_ids: {num_duplicates}")

    duplicate_rows = transactions_df[
        transactions_df["invoice_id"].duplicated(keep=False)
    ]
    duplicated_invoice_ids = duplicate_rows["invoice_id"].unique()
    if debug:
        print("Unique duplicated invoice_ids:")
        print(duplicated_invoice_ids)

    matched_rows_emails = ground_truth_df[
        ground_truth_df["invoice_id"].isin(duplicated_invoice_ids)
    ]
    email_id_associated_with_duplicated_invoice_id = matched_rows_emails[
        "email_id"
    ].tolist()
    return email_id_associated_with_duplicated_invoice_id


def print_row_details(df, indices=[0], columns=None):
    if columns is None:
        columns = df.columns
    for index in indices:
        for col in columns:
            print("-" * 50)
            print(f"{col}: {df[col].iloc[index]}")
        print("=" * 50)


def get_metrics(df, debug=False, including_df=False):
    if debug:
        print(f"Total number of tasks:\t\t{len(df)}")
        print(df["process_status"].value_counts())

    vc = df["process_status"].value_counts()
    completed = 1 - vc["NOT_STARTED"] / len(df) if "NOT_STARTED" in vc else 1

    if debug:
        print(f"Task completion rate:\t\t{completed * 100:.2f}%")

    # Calculate success rate
    success_rate = vc["SUCCESS"] / len(df) if "SUCCESS" in vc else 0
    if debug:
        print(f"Task success rate:\t\t{success_rate * 100:.2f}%")

    df["end_time"] = pd.to_datetime(df["end_time"])
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["duration"] = (df["end_time"] - df["start_time"]).dt.total_seconds()

    # Convert duration to HH:MM:SS format without milliseconds
    df["duration_hms"] = pd.to_timedelta(df["duration"], unit="s").dt.floor("s")

    if debug:
        print(f"Total execution time:\t\t{df['duration_hms'].sum()}")

    metrics = {
        "task_completion_rate": completed,
        "task_success_rate": success_rate,
        "mean_execution_time": df["duration"].mean(),
        "total_tasks": len(df),
        **df["process_status"].value_counts().to_dict(),
    }

    if "NOT_INVOICE" in metrics:
        metrics["NO_INVOICE"] = metrics["NOT_INVOICE"]
        del metrics["NOT_INVOICE"]
    else:
        metrics["NO_INVOICE"] = 0

    if including_df:
        metrics["df"] = df

    # Estimate remaining time
    if "NOT_STARTED" in vc:
        avg_duration = df[df["process_status"] != "NOT_STARTED"]["duration"].mean()
        remaining_tasks = vc["NOT_STARTED"]
        estimated_remaining_time = pd.to_timedelta(
            avg_duration * remaining_tasks, unit="s"
        ).floor("s")
        if debug:
            print(f"Estimated remaining time:\t{estimated_remaining_time}")

        metrics["estimated_remaining_time"] = estimated_remaining_time

    return metrics


def calculate_metrics(db_filepath, including_df=True, debug=False):
    conn = sqlite3.connect(db_filepath)

    # Write your SQL query
    query = "SELECT * FROM emails"

    # Read the query results into a pandas DataFrame
    df = pd.read_sql(query, conn)

    # Close the database connection
    conn.close()

    return get_metrics(df, debug=debug, including_df=including_df)


if __name__ == "__main__":
    db_filepath = "src/data/db/llama3.2-vision_11b-qwen2.5_7b/emails.db"
    metrics = calculate_metrics(db_filepath, including_df=True, debug=True)
    df = metrics["df"]
    del metrics["df"]
    print("metrics:", metrics)