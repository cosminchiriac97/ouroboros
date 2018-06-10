import FileModule
import requests
import json
import _thread
import time
import random
import subprocess
headers = {'Content-type': 'application/json'}


def open_mine(cont):
    requests.post(cont['address'] + 'mine', headers=headers)


conturi = []

subprocess.Popen('python Server.py 5000')
time.sleep(3)
cont = {
    'address': 'http://127.0.0.1:5000/'
}
_thread.start_new_thread(open_mine, (cont, ))
subprocess.Popen('python Server.py 5001')
time.sleep(2)
subprocess.Popen('python Server.py 5002')
time.sleep(2)
subprocess.Popen('python Server.py 5003')
time.sleep(2)
subprocess.Popen('python Server.py 5004')
time.sleep(3)


for port in range(5000, 5005):
    cont = {
        "cont": FileModule.get_account_by_port(port),
        "amount": 0
    }
    conturi.append(cont)

initial_transactions = []

for port in range(5001, 5005):
    trans = {
        'receiver_public_key': conturi[port-5000]['cont']['public_key'],
        'amount': random.randint(5000, 20000),
        'sender_public_key': conturi[0]['cont']['public_key'],
        'sender_private_key': conturi[0]['cont']['private_key']
    }
    conturi[0]['amount'] = conturi[0]['amount'] - trans['amount']
    conturi[port-5001]['amount'] = conturi[port-5001]['amount'] + trans['amount']
    initial_transactions.append(trans)

try:
    for port in range(5001, 5005):
        _thread.start_new_thread(open_mine, (conturi[port-5000]['cont'], ))
except Exception as e:
    print (str(e))


for tran in initial_transactions:
    response = requests.post(conturi[0]['cont']['address'] + 'transactions/new', data=json.dumps(tran), headers=headers)
    print(response.content)
while True:
    pass
