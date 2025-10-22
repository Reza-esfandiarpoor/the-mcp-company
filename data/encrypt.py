from cryptography.fernet import Fernet
import base64
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", type=str, default='/utils/evaluator.py', required=False, help='Input File')
parser.add_argument("-o", "--output", type=str, default='/utils/evaluator.py.enc', required=False, help='Output File')
args = vars(parser.parse_args())

# Hardcode the key value and encode it to bytes
key_bytes = b'theagentcompany is all you need'

# Pad the key to 32 bytes using the provided method
def pad_key(key):
    while len(key) < 32:
        key += b'\x00'
    return key[:32]

padded_key = pad_key(key_bytes)

# Get the Fernet instance
fernet = Fernet(base64.urlsafe_b64encode(padded_key))

# Encrypt the evaluator.py file using the Fernet instance
with open(args['input'], 'rb') as f:
    evaluator_content = f.read()

encrypted_evaluator = fernet.encrypt(evaluator_content)

with open(args['output'], 'wb') as f:
    f.write(encrypted_evaluator)
