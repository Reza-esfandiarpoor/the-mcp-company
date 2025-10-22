# python3 select_tools_for_task.py 'data/task_fn_matching_v0.json' 'admin-arrange-meeting-rooms'
# output: 'name1,name2,...,nameN'

import json
import sys
from pathlib import Path

assert len(sys.argv) == 3

filename, task_name = sys.argv[1:]

path = Path(__file__).parents[1].joinpath(filename)
assert path.exists()

with path.open("r") as f:
    all_sels = json.load(f)

output = list(set(all_sels[task_name]))

# output = ",".join(output)
print(json.dumps({"tool_names": output}))
