import json
import pickle

ACCOUNTS_FILENAME = r'D:\Licenta\ProofOfStake\Outputs\miners_accounts.json'
SECRET_SEEDS_PATH = 'Outputs\SecretSeeds\\'
CONFIG_FILE_PATH = 'ConfigFiles\\'


def init_accounts():
    with open(ACCOUNTS_FILENAME, mode='w', encoding='utf-8') as f:
        json.dump([], f)


def init_seeds(port):
    filename = SECRET_SEEDS_PATH + 'seed_' + port + '.txt'
    with open(filename, mode='w', encoding='utf-8') as f:
        json.dump([], f)


def append_account(account):
    with open(ACCOUNTS_FILENAME, mode='r', encoding='utf-8') as accountsjson:
        accounts = json.load(accountsjson)

    with open(ACCOUNTS_FILENAME, mode='w', encoding='utf-8') as accountsjson:
        accounts.append(account)
        json.dump(accounts, accountsjson)


def get_account_by_port(port):
    with open(ACCOUNTS_FILENAME, mode='r', encoding='utf-8') as accountsjson:
        accounts = json.load(accountsjson)

    for account in accounts:
        if str(port) in account['address']:
            return account


def append_secrets_to_file(port, seed):
    filename = SECRET_SEEDS_PATH + 'seed_' + port + '.txt'
    with open(filename, mode='a', encoding='utf-8') as seeds:
        seeds.write("epoch: " + str(seed['epoch']) + ' \n')
        seeds.write("slot: " + str(seed['slot']) + ' \n')
        seeds.write("seed: " + seed['seed'] + ' \n')
        for key in seed['openings']:
            seeds.write(key  + " " + str(seed['openings'][key]) + ' \n')
