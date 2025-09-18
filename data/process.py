import csv
import json
import os

base_folder = "data"
filenames = os.listdir(base_folder) # ["2024-06.json", "2024-07.json", "2024-08.json", "2024-09.json", "2024-10.json", "2024-11.json", "2024-12.json", "2025-01.json", "2025-02.json", "2025-03.json", "2025-03.json", "2025-04.json", "2025-05.json"]
filenames = [os.path.join(base_folder, file) for file in filenames if file.endswith(".json") or file.endswith(".csv")]

data: list[dict[str, str]] = []

for file in filenames:
    if file.endswith(".json"):
        with open(file, "r") as f:
            data.extend(json.load(f))
    else:
        with open(file, "r", newline="") as f:
            reader = csv.DictReader(f) # , fieldnames=["slot","parent_hash","block_hash","builder_pubkey","proposer_pubkey","proposer_fee_recipient","gas_limit","gas_used","value","num_tx","block_number","timestamp","timestamp_ms"]
            data.extend([row for row in reader])
            


values: list[int] = sorted([int(entry["value"]) / (10 ** 18) for entry in data])


avg_values = sum(values) / len(data)
slots_per_years = 365 * 3600 * 24 / 12
print("Average MEV upscaled with year:", avg_values * slots_per_years)
print("Average MEV: ", avg_values)
print("Median MEV:", values[len(values) // 2])
