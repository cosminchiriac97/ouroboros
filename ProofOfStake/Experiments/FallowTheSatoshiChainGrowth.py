"""
    Experiment 1:

    Input: 10 noduri care ruleaza protocolul timp te 30 de epoci

    Expected output: Se asteapta ca nodurile care au un stack mai mare sa fie alese de FallowSatoshi de mai multe ori in medie
"""
import FileModule
import json
import _thread
import time
import subprocess
import pause
import datetime
import requests

headers = {'Content-type': 'application/json'}
PORTS = []


def open_mine(cont):
    requests.post(cont['address'] + 'mine', headers=headers)


for i in range(9):
    PORTS.append(str(5001+i))


accounts = []
# Step1: Open root server
subprocess.Popen('python ../Server.py 5000')
time.sleep(3)
date = datetime.datetime.now()

cont = {
    'address': 'http://127.0.0.1:5000/'
}
_thread.start_new_thread(open_mine, (cont, ))

# Step2: open rest of servers
for port in PORTS:
    subprocess.Popen('python ../Server.py ' + port)
    time.sleep(1)
time.sleep(2)
# Get accounts
for port in range(5000, 5010):
    accounts.append(FileModule.get_account_by_port(port))

# distributes the stack
initial_transactions = []

amounts = [25000, 15000, 10000, 5000, 4500, 4000, 3000, 2000, 1000]
for port in range(5001, 5010):
    trans = {
        'receiver_public_key': accounts[port-5000]['public_key'],
        'amount': amounts[port-5001],
        'sender_public_key': accounts[0]['public_key'],
        'sender_private_key': accounts[0]['private_key']
    }

    initial_transactions.append(trans)

try:
    for port in range(5001, 5010):
        _thread.start_new_thread(open_mine, (accounts[port-5000], ))
except Exception as e:
    print(str(e))

for tran in initial_transactions:
    response = requests.post(accounts[0]['address'] + 'transactions/new', data=json.dumps(tran), headers=headers)
    print(response.content)

dd = date + datetime.timedelta(seconds=3*7*5)
time.sleep(7*5*3)

chains = []

for account in accounts:
    response = requests.get(url=account['address'] + 'chain', headers=headers)
    if response.status_code == 200:
        resp_data = response.json()
        chains.append(resp_data)

new_responses = sorted(chains, key=lambda k: k['length'], reverse=True)

block_count = {}
for block in chains[0]['chain']:
    if block['block_type'] == 'genesis' and block['epoch'] > 1:
        for slot_leader in block['slot_leaders']:
            if slot_leader['address'] in block:
                block_count[slot_leader['address']] = block_count[slot_leader['address']] + 1
            else:
                block_count[slot_leader['address']] = 1

for key in block_count:
    print(key + ' ' + str(block_count[key]))
