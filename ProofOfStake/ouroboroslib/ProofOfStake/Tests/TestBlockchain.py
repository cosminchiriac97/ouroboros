import BlockChain, Stakeholder
import json
import pprint
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import time

wallet1 = BlockChain.BlockChain.generate_new_wallet()

def build_new_blocks(scheduler, blockchain):
    slot, seconds_till_the_next_slot = blockchain.get_current_slot()
    dd = datetime.now() + timedelta(miliseconds=seconds_till_the_next_slot*1000)

    scheduler.add_job(build_new_blocks, 'date', run_date=dd, kwargs={'scheduler': scheduler, 'blockchain': blockchain})
    if(slot <5):
        blockchain.forge_new_block()
    else:
        blockchain.new_genesis_block()

stakeholder = Stakeholder.Stakeholder(wallet1['public_key'], "http://127.0.0.1:" + str(5000) + "/", wallet1['wallet_address'])

blockchain = BlockChain.BlockChain(True, stakeholder, wallet1['private_key'])

print(blockchain.get_current_slot())
print(blockchain.get_current_epoch())
time.sleep(6)
print(blockchain.get_current_slot())
print(blockchain.get_current_epoch())
"""
wallet2 = BlockChain.BlockChain.generate_new_wallet()

wallet3 = BlockChain.BlockChain.generate_new_wallet()

blockchain.register_new_node(wallet3['public_key'], "http://127.0.0.1:5001", wallet3['wallet_address'])

transaction = {
    "sender_address": wallet1['wallet_address'],
    "sender_public_key": wallet1['public_key'],
    "recipient_address": wallet2['wallet_address'],
    "reward": 0.002,
    "amount": 100,
    "sender_private_key": wallet1['private_key']
}

result = blockchain.new_transaction(transaction)

blockchain.forge_new_block()

pprint.pprint(json.loads(json.dumps(blockchain.chain[0])))
pprint.pprint(json.loads(json.dumps(blockchain.chain[1])))


##print(blockchain.get_amount(wallet2['wallet_address']))
"""