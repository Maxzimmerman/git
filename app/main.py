import sys
import os
import zlib


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!", file=sys.stderr)

    command = sys.argv[1]
    if command == "init":
        os.mkdir(".git")
        os.mkdir(".git/objects")
        os.mkdir(".git/refs")
        with open(".git/HEAD", "w") as f:
            f.write("ref: refs/heads/main\n")
        print("Initialized git directory")
    elif command == "cat-file":
        blob_hash = sys.argv[3]
        obj_path = f".git/objects/{blob_hash[:2]}/{blob_hash[2:]}"
        with open(obj_path, "rb") as f:
            decompressed = zlib.decompress(f.read())
        null_idx = decompressed.index(b"\x00")
        sys.stdout.buffer.write(decompressed[null_idx + 1:])
    elif command == "hash-object":
        print("hash-object")
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
