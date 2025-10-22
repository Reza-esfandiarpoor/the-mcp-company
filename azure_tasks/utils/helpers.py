import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import Client
from rich.pretty import pprint


def write_json(obj: Any, path: str | Path):
    """Writes an object to a json file and creates the parent directories if necessary."""
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def aggregate_and_format_results(checkpoints: List[Dict[str, float]]) -> Dict:
    """Aggreates the results from checkpoints and formats them in a way that is compatible with TheAgentCompany.

    Args:
        checkpoints: a list of checkpoint results. Each item in the list is a dictionary with two enteries 'total' and 'result'.
            'total' is the max score that the agent can get for this checkpoint. 'result' is the score that the agent actually got for this checkpoint.

    Returns:
        A dict like the following:
        {
          "checkpoints": [
              {
              "total": 1, // total score for this checkpoint
              "result": 1 // the score that the agent got for this checkpoint
              },
              { // next checkpoint
              "total": 2,
              "result": 0
              },
          "final_score": {
              "total": 3, // this is the sum of the 'total' for all checkpoints
              "result": 1 // this is the sum of the 'result' for all checkpoints
              }
          ]
        }
    """
    total = 0
    result = 0
    for ckpt in checkpoints:
        total += ckpt["total"]
        result += ckpt["result"]
    eval_result = {
        "checkpoints": checkpoints,
        "final_score": {"total": total, "result": result},
    }
    print(eval_result)
    return eval_result


def check_output_filepath(argv: List):
    """Make sure the commandline args contain correct output filepath and return it"""
    if len(argv) != 2:
        raise ValueError(
            "You should call this script with an output filepath like python evaluate.py myfile.json"
        )
    assert argv[1].endswith(".json")
    output_path = argv[1]
    return output_path
