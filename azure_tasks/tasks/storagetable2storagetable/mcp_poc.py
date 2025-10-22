import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####


sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
storage_acct = f"sacct{exp_uuid}"

table1 = "Table1"
table2 = "Table2"

copyme = azure_mcp_ops.get_table_entities(storage_acct, table1)

for entity in copyme:
    del entity["Timestamp"]
    azure_mcp_ops.insert_row_into_table(storage_acct, table2, entity)
