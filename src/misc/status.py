from sys import argv
from metrics import calculate_metrics, get_metrics


def print_metrics(msg, metrics):
    print(msg)
    for key, value in metrics.items():
        print(f"\t{key}: {value}")
    print()


if __name__ == "__main__":
    db_filepath = argv[1]
    print(f"Calculating metrics for {db_filepath}...")

    metrics = calculate_metrics(db_filepath, including_df=True)
    df = metrics["df"]
    del metrics["df"]
    print_metrics("metrics:", metrics)
