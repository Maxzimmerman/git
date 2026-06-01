import sys, zlib
from .base import Command

class CatFile(Command):
    def execute(self, args):
        blob_hash = sys.argv[3]
        print(blob_hash[:2])
        print(blob_hahs[2:])
        obj_path = f".git/objects/{blob_hash[:2]}/{blob_hash[2:]}"
        with open(obj_path, "rb") as f:
            decompressed = zlib.decompress(f.read())
        null_idx = decompressed.index(b"\x00")
        sys.stdout.buffer.write(decompressed[null_idx + 1:])
