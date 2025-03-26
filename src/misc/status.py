import sys
import os
from metrics import calculate_metrics, get_metrics


def print_metrics(msg, metrics):
    print(msg)
    for key, value in metrics.items():
        print(f"\t{key}: {value}")
    print()


def print_usage():
    print("Usage: python status.py <path_to_directory_containing_db>")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: No directory path provided.")
        print_usage()
        sys.exit(1)

    directory = sys.argv[1]
    db_filepath = os.path.join(directory, "emails.db")
    print(f"Calculating metrics for {db_filepath}...\n")

    metrics = calculate_metrics(db_filepath, including_df=True)
    df = metrics.pop("df", None)

    print_metrics("Metrics:", metrics)
