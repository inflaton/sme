import os
import sys
from pathlib import Path
from dotenv import find_dotenv, load_dotenv
import pandas as pd
from metrics import *

def print_usage():
    print("Usage: python src/misc/calc_metrics.py <path_to_directory_containing_results> <platform>")

if len(sys.argv) < 3:
    print("Error: No directory path and/or platform provided.")
    print_usage()
    sys.exit(1)

directory = sys.argv[1]
platform = sys.argv[2]
print(f"Calculating metrics for directory: {directory} for platform: {platform} ...")

found_dotenv = find_dotenv(".env")

if len(found_dotenv) == 0:
    found_dotenv = find_dotenv(".env.example")
print(f"loading env vars from: {found_dotenv}")
load_dotenv(found_dotenv, override=True)

subfolders = ["llama3.2-vision_11b-qwen2.5_7b",
    "llama3.2-vision_11b-functionary-small",
    "llama3.2-vision_11b-qwen2.5_32b",
    "llama3.2-vision_11b-functionary-medium",
    "llama3.2-vision_11b-qwen2.5_72b",
    "gpt-4o-mini-gpt-4o-mini",
    "gpt-4o-gpt-4o"]

def total_power_in_watt(file_path):
    df = pd.read_csv(file_path)
    return df["CPU Package Power [W]"].mean() + df["GPU Power [W]"].mean()

# Initialize an empty DataFrame
metrics_df = pd.DataFrame()

for subfolder in subfolders:
    dir = f"{directory}/{subfolder}"
    if os.path.isdir(dir):
        model = subfolder.replace("gpt-4o-mini-", "").replace("gpt-4o-gpt", "gpt").replace("llama3.2-vision_11b-", "")
        print(f"Calculating metrics for model: model{model}...")
        
        db_filepath = f"{dir}/emails.db"
        metrics = calculate_metrics(db_filepath)
        df = metrics["df"]
        metrics = get_metrics(df)

        try:
            power = total_power_in_watt(
                f"results/{platform}_{model}/power_with_vision.csv"
            )

            idle_power_csv = f"results/power_idle_{platform}.csv"
            if not Path(idle_power_csv).exists():
                idle_power_csv = "results/power_idle.csv"
            power -= total_power_in_watt(idle_power_csv)

            metrics["power"] = power
        except FileNotFoundError:
            print(f"Power data not found for model: model{model}")

        # Add non-metric columns and metrics to a single dictionary
        row_data = {"platform": platform, "model": model, **metrics}
        metrics_df = pd.concat(
            [metrics_df, pd.DataFrame([row_data])], ignore_index=True
        )

metrics_df.to_csv(f"results/metrics_{platform}.csv", index=False)
print(f"Metrics saved as results/metrics_{platform}.csv")
