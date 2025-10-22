import hashlib
import json
import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

sys.path.append(Path(__file__).parent.as_posix())
from init_table import entities

output_path = helpers.check_output_filepath(sys.argv)

####


sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
account_name = f"sacct{exp_uuid}"


def hash_obj_list(obj_list):
    obj_map = dict()
    for ent in obj_list:
        ent.pop('Timestamp', None)
        ent_sorted = {k: ent[k] for k in sorted(ent)}
        ent_hash = hashlib.sha256(json.dumps(ent_sorted).encode()).hexdigest()
        obj_map[ent_hash] = ent
    return obj_map


gold_objs = hash_obj_list(entities)
new_objs = azure_ops.get_table_entities(account_name, "Table2")
new_objs = hash_obj_list(new_objs)

gold_keys = set(list(gold_objs.keys()))
new_keys = set(list(new_objs.keys()))

checkpoints = []
if gold_keys == new_keys:
    checkpoints.append({"total": 1, "result": 1})
else:
    print("Gold Rows")
    pprint(list(gold_objs.values()))
    print()
    print("New Rows")
    pprint(list(new_objs.values()))

    checkpoints.append({"total": 1, "result": 0})


output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
