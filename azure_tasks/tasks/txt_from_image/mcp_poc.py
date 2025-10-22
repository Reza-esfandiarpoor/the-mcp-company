import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####

exp_uuid = os.environ["EXP_UUID"]
vision_acct = f"vis{exp_uuid}"
vision_domain = f"domain{exp_uuid}"
storage_acct = f"sacct{exp_uuid}"
container_name = "txtfromimagectr"

image_name = "image.png"

image_url = (
    f"https://{storage_acct}.blob.core.windows.net/{container_name}/{image_name}"
)
print("image url:")
print(image_url)
print()

result = azure_mcp_ops.ocr_read(vision_domain, image_url)
print("result text:")
print(result)

azure_mcp_ops.write_to_blob(storage_acct, container_name, "result.txt", result)
