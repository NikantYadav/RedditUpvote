import json
import os

def add_proxy(proxy: str):
    proxypath = "../proxies.json"

    
    if os.path.exists(proxypath):
        try:
            with open(proxypath, 'r') as f:
                proxies = json.load(f)
        except json.JSONDecodeError:
            proxies = []
    else:
        proxies = []

    
    if proxy not in proxies:
        proxies.append(proxy)
        with open(proxypath, 'w') as f:
            json.dump(proxies, f)

    accountpath = "../accounts.json"

    
    if os.path.exists(accountpath):
        try:
            with open(accountpath, 'r') as a:
                accounts = json.load(a)
        except json.JSONDecodeError:
            accounts = []
    else:
        accounts = []

    for i, account in enumerate(accounts):
        if i < len(proxies):
            if isinstance(account, dict):
                account["proxy"] = proxies[i]
            elif isinstance(account, list):
                account.append(proxies[i])

    with open(accountpath, 'w') as f:
        json.dump(accounts, f, indent=4)
