import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
resource_group = "azuretasks_cross_translate"
acct_name = f"trname{exp_uuid}"

endpoint = "https://api.cognitive.microsofttranslator.com"
storage_acct = f"sacct{exp_uuid}"
unsorted_ctr = "sort-me"
orig_en = "orig-en"
orig_fa = "orig-fa"
orig_other = "orig-other"
en_to_fa = "en-to-fa"
fa_to_en = "fa-to-en"


file2orig = {"doc1.txt": "en", "doc2.txt": "fa", "doc3.txt": "fa", "doc4.txt": "en"}

expect_orig_en = [fl for fl in file2orig if file2orig[fl] == "en"]
expect_orig_fa = [fl for fl in file2orig if file2orig[fl] == "fa"]

checkpoints = list()


def ckpt(sc):
    checkpoints.append({"total": 1, "result": sc})


for fl in expect_orig_en:
    if not azure_ops.blob_exists(storage_acct, orig_en, fl):
        print(f"{fl} not found in orig-en")
        ckpt(0)
    else:
        ckpt(1)

    if not azure_ops.blob_exists(storage_acct, en_to_fa, fl):
        print(f"{fl} not found in en-to-fa")
        ckpt(0)
    else:
        ckpt(1)

for fl in expect_orig_fa:
    if not azure_ops.blob_exists(storage_acct, orig_fa, fl):
        print(f"{fl} not found in orig-fa")
        ckpt(0)
    else:
        ckpt(1)

    if not azure_ops.blob_exists(storage_acct, fa_to_en, fl):
        print(f"{fl} not found in fa-to-en")
        ckpt(0)
    else:
        ckpt(1)

# Now make sure each of the files is in the expected language
for fl in expect_orig_en:
    if not azure_ops.blob_exists(storage_acct, en_to_fa, fl):
        ckpt(0)
    else:
        xlated_txt = azure_ops.read_text_from_blob(storage_acct, en_to_fa, fl)
        detection = azure_ops.langdetect_txt(
            sub_id, resource_group, acct_name, endpoint, xlated_txt
        )
        if detection != "fa":
            print(f"Expected Farsi in {en_to_fa}/{fl}, got {detection}")
            ckpt(0)
        else:
            ckpt(1)

for fl in expect_orig_fa:
    if not azure_ops.blob_exists(storage_acct, fa_to_en, fl):
        ckpt(0)
    else:
        xlated_txt = azure_ops.read_text_from_blob(storage_acct, fa_to_en, fl)
        detection = azure_ops.langdetect_txt(
            sub_id, resource_group, acct_name, endpoint, xlated_txt
        )
        if detection != "en":
            print(f"Expected English in {fa_to_en}/{fl}, got {detection}")
            ckpt(0)
        else:
            ckpt(1)

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
