import BlockChain
import EcdsaSigning, Stakeholder
import copy


private_key, public_key = EcdsaSigning.generate_keys()
account = {
    "private_key": private_key,
    "public_key": public_key,
    "address": "http://127.0.0.1:" + str(5000) + "/"
}
private_key1, public_key1 = EcdsaSigning.generate_keys()
account2 = {
    "private_key": private_key1,
    "public_key": public_key1,
    "address": "http://127.0.0.1:" + str(5001) + "/"
}

private_key2, public_key2 = EcdsaSigning.generate_keys()
account3 = {
    "private_key": private_key2,
    "public_key": public_key2,
    "address": "http://127.0.0.1:" + str(5002) + "/"
}

stakeholder = Stakeholder.Stakeholder(account['public_key'], account['address'])


block_chain = BlockChain.BlockChain(True, stakeholder, account['private_key'])


values = {
    'receiver_public_key': account2['public_key'],
    'amount': 10000,
    'sender_public_key': account['public_key'],
    'sender_private_key': account['private_key']
}

values1 = {
    'receiver_public_key': account3['public_key'],
    'amount': 10000,
    'sender_public_key': account['public_key'],
    'sender_private_key': account['private_key']
}

values2 = {
    'receiver_public_key': account['public_key'],
    'amount': 5000,
    'sender_public_key': account2['public_key'],
    'sender_private_key': account2['private_key']
}

transaction = block_chain.new_transaction(values)
transaction2 = block_chain.new_transaction(values1)
transaction3 = block_chain.new_transaction(values2)

trans = copy.deepcopy(block_chain.transactions[1])


block_chain.add_transaction_from_internet(trans)

block_chain.forge_new_block(account['private_key'])
block_chain.forge_new_block(account['private_key'])

walllets = {}

walllets[account['public_key']] = 0
walllets[account2['public_key']] = 0
walllets[account3['public_key']] = 0
print(block_chain.get_amount_genesis_stakeholders(walllets))
