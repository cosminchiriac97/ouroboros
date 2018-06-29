import FileModule
import json
import requests
headers = {'Content-type': 'application/json'}

cont1 = FileModule.get_account_by_port(5000)
cont2 = FileModule.get_account_by_port(5005)

data = {
    'receiver_public_key': cont2['public_key'],
    'amount': 30000,
    'sender_public_key': cont1['public_key'],
    'sender_private_key': cont1['private_key']
}


requests.post(cont1['address']+'transactions/new', data=json.dumps(data), headers=headers)


