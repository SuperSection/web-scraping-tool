import json
import csv
import os


def save_to_json(data, filepath="output/results.json"):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[✓] Saved JSON to {filepath}")


def save_to_csv(data: list[dict], filepath="output/results.csv"):
    """
    Saves the extracted company data to a CSV file.

    Args:
        data (list): A list of dictionaries, with each dictionary representing a company.
        filepath (str): The path of the CSV file to save to.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if not data:
        print("[!] No data to write to CSV.")
        return

    keys = data[0].keys()
    with open(filepath, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=keys)
        writer.writeheader()
        for row in data:
            flat_row = {k: ", ".join(v) if isinstance(v, list) else v for k, v in row.items()}
            writer.writerow(flat_row)
    print(f"[✓] Saved CSV data to {filepath}")
