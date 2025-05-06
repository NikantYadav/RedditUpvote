import json
import os

def add_account(username: str, password: str):
    filepath = '../accounts.json'

    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            try:
                accounts = json.load(f)
            except json.JSONDecodeError:
                accounts = []
    else:
        accounts = []

    accounts.append({"username": username, "password": password})


    with open(filepath, 'w') as f:
        json.dump(accounts, f)

if __name__ == "__main__":
    number = int(input("Enter number of accounts you want to add: "))
    while number!=0:
        username = input("Enter username: ")
        password = input("Enter Password: ")
        add_account(username, password)
        print("Account Added")
        number = number - 1
    