import random
import os

def create_file():
    with open(os.getcwd() + "/dummy_file", "w", encoding="utf8") as rf:
        rf.write(f"Dummy.sh: {random.randint(1, 10000000)}")

if __name__ == "__main__":
    create_file()
