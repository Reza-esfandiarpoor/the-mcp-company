import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops

exp_uuid = os.environ["EXP_UUID"]

account_name = f"sacct{exp_uuid}"
table_name = "Table1"
partition_key = "partition1"

# PartitionKey + RowKey required
# anthaue forgot to add more!
entities = [
    {
        "Name": "Alice",
        "Age": 30,
        "FavoriteIceCream": "Chocolate",
        "PartitionKey": partition_key,
        "RowKey": "Alice",
    },
    {
        "Name": "Bob",
        "Age": 45,
        "FavoriteIceCream": "Vanilla",
        "PartitionKey": partition_key,
        "RowKey": "Bob",
    },
]

if __name__ == "__main__":
    for entity in entities:
        azure_ops.add_row_to_table(account_name, table_name, entity)
