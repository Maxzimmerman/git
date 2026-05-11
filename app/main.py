import sys
import os


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
        print("cat-file")
        print(os.listdir(".git/objects"))
        with open(f".git/objects/{os.listdir(".git/objects")[0][1]}") as f:
            print(f.read())
    elif command == "hash-object":
        print("hash-object")
    else:
        raise RuntimeError(f"Unknown command #{command}")


if __name__ == "__main__":
    main()
