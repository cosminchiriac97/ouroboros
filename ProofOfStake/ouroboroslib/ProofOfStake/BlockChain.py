""""
    Implementation for the block chain
    chain - holds the entire block chain
    transaction -

    epoch - 30 seconds
    slot - 5 seconds
"""

import time, requests, hashlib, Stakeholder, EcdsaSigning, secrets, json, base64,  copy, FileModule, random
import FollowTheSatoshi
from dateutil import parser
from datetime import datetime, timedelta
import asyncio
from aiohttp import ClientSession
import sys

MIN_FEES = 0.01
headers = {'Content-type': 'application/json'}


class BlockChain(object):

    def __init__(self, is_first_node, my_profile, my_private_key):
        self.chain = []
        self.transactions = []
        self.peers = set()
        self.pending_peers = set()
        self.my_profile=my_profile
        self.my_private_key = my_private_key
        self.commitments = []
        self.openings = []
        self.my_commitment = {}
        self.peers_for_reveal = []
        self.my_opening = None
        self.seed = None
        self.my_seeds = {}
        self.is_first_node = is_first_node
        if is_first_node:
            self.generate_first_genesis_block()
        self.last_seed = {
            "epoch": 0,
            "seed": 'first-genesis-block'
        }
        self.can_vote = False

    def register_new_node(self, public_key, address):
        stakeholder = Stakeholder.Stakeholder(public_key, address)
        if address == 'http://127.0.0.1:5000/':
            self.peers.add(stakeholder)
        else:
            peers = copy.deepcopy(self.peers)
            for peer in peers:
                if peer.address == address:
                    self.peers.remove(peer)
            pending_peers = copy.deepcopy(self.pending_peers)
            for pending_peer in pending_peers:
                if pending_peer.address == address:
                    self.pending_peers.remove(pending_peer)
            self.pending_peers.add(stakeholder)

    def get_nodes(self):
        peers_list = copy.deepcopy(self.peers)
        for peer in self.pending_peers:
            peers_list.add(peer)
        return list(peers_list)

    def get_pending_peers(self):
        return list(self.pending_peers)

    def new_transaction(self, values):

        total_coins, unspent_outputs = self.get_amount(values['sender_public_key'])
        if values['amount'] + MIN_FEES > total_coins:
            return False, 'Not enough coins'

        outputs = []
        inputs = []
        amount = 0
        for key in unspent_outputs:
            previous_out = {
                "hash": unspent_outputs[key]['transaction-hash'],
                "index": unspent_outputs[key]['id']
            }

            signature = EcdsaSigning.sign_data(values['sender_private_key'], json.dumps(previous_out))

            if EcdsaSigning.verify_sign(values['sender_public_key'], signature, json.dumps(previous_out)):
                amount = amount + unspent_outputs[key]['value']
                input = {
                    "previous_out": previous_out,
                    "signature": signature
                }
                inputs.append(input)

            if amount + MIN_FEES >= values['amount']:
                break

        if amount + MIN_FEES < values['amount']:
            return False, 'Not enough coins'

        output = {
            "value": values['amount'],
            "public_key": values['receiver_public_key']
        }
        outputs.append(output)
        if amount - MIN_FEES - values['amount'] > 0:
            change = {
                "value": amount - MIN_FEES - values['amount'],
                "public_key": values['sender_public_key']
            }
            outputs.append(change)

        date = str(datetime.now())
        transaction = {
            "hash": hashlib.sha256(base64.b64encode((json.dumps(inputs) +
                                                    json.dumps(outputs) + date).encode('utf-8'))).hexdigest(),
            "size": sys.getsizeof(json.dumps(inputs) + json.dumps(outputs) + date),
            "date": date,
            "inputs": inputs,
            "outputs": outputs
        }

        # broadcast transaction to all neighborhoods
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(self.run_broadcast_new_transaction(json.dumps(transaction)))
        loop.run_until_complete(future)

        self.transactions.append(transaction)
        return True, 'Transaction will be added to the block chain'

    def add_transaction_from_internet(self, transaction):
        transactions = copy.deepcopy(self.transactions)
        resp = BlockChain.verify_transaction(self.chain, transaction, transactions)

        if resp[0]:
            self.transactions.append(transaction)
            return resp, resp[1]
        else:
            return resp, resp[1]

    def forge_new_block(self, private_key):
        # Step1: check double spend situations
        transactions_for_forge = list()
        fees_values = 0
        transaction_len = copy.deepcopy(len(self.transactions))
        transactions = copy.deepcopy(self.transactions)
        i = 0
        while i < transaction_len:
            i = i + 1
            trans = copy.deepcopy(transactions[0])
            del transactions[0]
            result = BlockChain.verify_transaction(self.chain, trans, transactions)
            if result[0]:
                transactions_for_forge.append(trans)
                fees_values = fees_values + result[2]
            transactions.append(trans)

        # Step2: collect fees
        if fees_values != 0:
            previous_out = {
                "hash": hashlib.sha256(
                    base64.b64encode(json.dumps(self.chain[-1], sort_keys=True).encode('utf-8'))).hexdigest(),
                'index': -2
            }

            signature = EcdsaSigning.sign_data(self.my_private_key, json.dumps(previous_out))

            input = {
                "previous_out": previous_out,
                "signature": signature
            }

            output = {
                "value": fees_values,
                "public_key": self.my_profile.public_key
            }
            date = str(datetime.now())

            transaction = {
                "hash": hashlib.sha256(base64.b64encode((json.dumps([input]) +
                                                         json.dumps([output]) + date).encode('utf-8'))).hexdigest(),
                "size": sys.getsizeof(json.dumps([input]) + json.dumps([output]) + date),
                "date": date,
                "inputs": [input],
                "outputs": [output]
            }

            transactions_for_forge.append(transaction)

        # Step3: Forge a new block
        block = {
            'block_type': "epoch",
            'index': len(self.chain) + 1,
            'epoch': self.get_current_epoch()[0],
            'slot': self.get_current_slot()[0],
            'address': self.my_profile.address,
            'public_key': self.my_profile.public_key,
            'previous_block_hash': hashlib.sha256(base64.b64encode(json.dumps(self.chain[-1], sort_keys=True).encode('utf-8'))).hexdigest(),
            'signature': EcdsaSigning.sign_data(private_key, json.dumps(self.chain[-1], sort_keys=True)),
            'transactions': copy.deepcopy(transactions_for_forge),
            'date': str(datetime.now())
        }

        hash_trans_list = []
        for trans in transactions_for_forge:
            hash_trans_list.append(trans['hash'])

        # Step4: append block to block chain and clear transaction list
        self.chain.append(block)

        # Step5: broadcast block to 4-5 next slot leaders
        epoch = self.get_current_epoch()[0]
        if epoch != 0:
            genesis_block = self.last_genesis_block()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            future = asyncio.ensure_future(self.run_broadcast_new_epoch_block(genesis_block))
            loop.run_until_complete(future)


        i = 0
        while i < len(self.transactions):
            if self.transactions[i]['hash'] in hash_trans_list:
                del self.transactions[i]
                i = i-1
            i = i+1

        return block

    def generate_first_genesis_block(self):

        transaction = {
            'hash': 'first-transaction',
            'size': 0,
            'date': str(datetime.now()),
            'inputs': [
                {
                    "previous_out": {
                        "hash": 'first-transaction',
                        'index': -1
                    },

                    "signature": 0
                }
            ],
            'outputs': [
                {
                    "value": 100000,
                    'public_key': self.my_profile.public_key
                }
            ]
        }
        transaction['inputs'][0]['signature'] = EcdsaSigning.sign_data(self.my_private_key,
                                                                       json.dumps(transaction['inputs'][0]['previous_out']))
        start_date = str(datetime.now())

        message_first_genesis = 'first-genesis' + str(0) + str(0) + 'first-genesis-block' + json.dumps(transaction) +\
                                self.my_profile.address + str(datetime.now())

        genesis_stake_holder = Stakeholder.GenesisStakeholder(100000, self.my_profile.public_key,
                                                              self.my_profile.address)

        first_genesis_block = {
            'block_type': "first-genesis",
            'epoch': 0,
            'slot': -1,
            'address': self.my_profile.address,
            'seed': 'first-genesis-block',
            'transactions': [transaction],
            'genesis_stakeholders': [genesis_stake_holder.to_json()],
            'start_date': start_date,
            'signature': EcdsaSigning.sign_data(self.my_private_key, message_first_genesis)
        }

        self.chain.append(first_genesis_block)

    def new_genesis_block(self, private_key):

        for peer in self.pending_peers:
            self.peers.add(peer)

        self.pending_peers = set()
        last_genesis_block = self.last_genesis_block()
        if last_genesis_block is None:
            last_genesis_block = self.chain[0]
        list_stakeholders = list()
        for stakeholder in last_genesis_block['genesis_stakeholders']:
            self.peers.add(Stakeholder.Stakeholder(stakeholder['public_key'], stakeholder['address']))
            list_stakeholders.append(Stakeholder.GenesisStakeholder(stakeholder['coins'], stakeholder['public_key'], stakeholder['address']))

        markle_tree = FollowTheSatoshi.generate_merkle_tree(list_stakeholders, last_genesis_block['seed'])
        slot_leaders = list()

        for i in range(8):
            slot_leader = FollowTheSatoshi.pick_random_stake_holder(markle_tree, last_genesis_block['seed']+str(i))
            slot_leaders.append({
                'coins': slot_leader.coins,
                'public_key': slot_leader.public_key,
                'address': slot_leader.address
            })

        ##Create a dictionary for calculation of amount for each users

        wallets = {}
        for peer in self.peers:
            wallets[peer.public_key] = 0

        wallets = self.get_amount_genesis_stakeholders(wallets)
        genesis_stakeholder_list = list()

        for peer in self.peers:
            if wallets[peer.public_key] > 0:
                genesis_stakeholder_list.append({
                    'coins': wallets[peer.public_key],
                    'public_key': peer.public_key,
                    'address': peer.address
                })
        genesis_block = {
            'block_type': "genesis",
            'epoch': self.get_current_epoch()[0]+1,
            'slot': self.get_current_slot()[0],
            'seed': self.seed,
            'public_key': self.my_profile.public_key,
            'slot_leaders': slot_leaders,
            'genesis_stakeholders': genesis_stakeholder_list,
            'previous_block_hash': hashlib.sha256(base64.b64encode(json.dumps(self.chain[-1], sort_keys=True).encode('utf-8'))).hexdigest(),
            'signature': EcdsaSigning.sign_data(private_key, json.dumps(self.chain[-1], sort_keys=True)),
            'date': str(datetime.now())
        }

        self.chain.append(genesis_block)
        # broadcast the result

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(self.run_broadcast_new_genesis_block(genesis_block))
        loop.run_until_complete(future)

        return genesis_block

    def get_current_epoch(self):
        d1 = parser.parse(self.chain[0]['start_date'])
        d2 = datetime.now()
        seconds = (d2-d1).total_seconds()
        current_epoch = int(seconds/40)
        seconds_till_the_next_epoch = (current_epoch+1)*40 - (d2-d1).total_seconds()
        return current_epoch, seconds_till_the_next_epoch

    def get_current_slot(self):
        d1 = parser.parse(self.chain[0]['start_date'])
        d2 = datetime.now()
        seconds = (d2 - d1).total_seconds()
        current_epoch = int(seconds / 40)
        current_slot = int((d2-d1).total_seconds()-current_epoch*40)/5
        seconds_till_the_next_slot = current_epoch*40 + ((int(current_slot)+1)*5) - (d2-d1).total_seconds()
        return int(current_slot), seconds_till_the_next_slot

    def last_genesis_block(self):
        for block in reversed(self.chain):
            if block['block_type'] == "genesis":
                    return block
        return self.chain[0]

    def verify_block_chain(self, block_chain):
        headers = {'Content-type': 'application/json'}
        # verify len first

        if len(block_chain) <= len(self.chain):
            return False, -1

        epoch = self.get_current_epoch()[0]
        slot = self.get_current_slot()[0]
        if len(block_chain) > epoch*7 + slot+2:
            return False, -1

        # check first block
        if len(self.chain) > 0:
            if json.dumps(self.chain[0], sort_keys=True) != json.dumps(block_chain[0], sort_keys=True):
                return False, -1

        # verify hash
        index = 1
        while True:
            if index >= len(self.chain):
                break

            new_block_chain_hash = hashlib.sha256(base64.b64encode(json.dumps(block_chain[index-1], sort_keys=True).
                                                                   encode('utf-8'))).hexdigest()
            my_hash = self.chain[index]['previous_block_hash']
            if new_block_chain_hash != my_hash:
                break
            index = index + 1
        
        index_for_rollback = index

        # verify signature
        while True:
            if index >= len(block_chain):
                break
            new_block_chain_public_key = block_chain[index]['public_key']

            rand = random.randint(1, 30)
            if rand == 25:
                try:
                    response = requests.get(block_chain[index]['address'] + 'public_key', headers=headers)
                    if response.status_code == 200:
                        response_data = response.json()
                        new_block_chain_public_key = response_data['public_key']
                except Exception as e:
                    pass

            if not EcdsaSigning.verify_sign(new_block_chain_public_key, block_chain[index]['signature'],
                                            json.dumps(block_chain[index-1], sort_keys=True)):
                return False, -1
            # verify seeds and slot leaders
            if block_chain[index]['block_type'] == 'genesis':
                for i in range(index-1, 1, -1):
                    if block_chain[i]['block_type'] == 'genesis':
                        if block_chain[index]['epoch'] == block_chain[i]['epoch']:
                            return False, -1

                pass

            index = index+1
        if index_for_rollback <= len(self.chain):
            index_for_rollback = -1

        return True, index_for_rollback

    def verify_transactions_in_consensus_algorithm(self, index, new_block_chain):

        verified_transactions = []
        if index > -1:
            for i in range(index, len(new_block_chain)):
                for trans in new_block_chain[i]['transactions']:
                    result = BlockChain.verify_transaction(self.chain, trans, verified_transactions)
                    print(result[1])
                    if not result[0]:
                        return False
                    verified_transactions.append(trans)
        return True

    def consensus_algorithm(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(self.run_consensus_algorithm())
        loop.run_until_complete(future)

    def commitment_phase(self, private_key, scheduler):
        slot, seconds_till_the_next_slot = self.get_current_slot()

        dd = datetime.now() + timedelta(seconds=(7-slot) * 5 + seconds_till_the_next_slot)

        scheduler.add_job(self.commitment_phase, 'date', run_date=dd,
                          kwargs={'private_key': private_key, 'scheduler': scheduler})
        byte_array = b"\x00" + secrets.token_bytes(8) + b"\x00"
        self.my_opening = base64.b64encode(byte_array).decode('utf-8')
        commitment = EcdsaSigning.sign_data(private_key, self.my_opening)
        self.my_commitment = {
            'public_key': self.my_profile.public_key,
            'commitment': commitment
        }
        self.consensus_algorithm()

        last_genesis_block = self.last_genesis_block()
        if last_genesis_block['block_type'] == 'genesis':
            for peers in last_genesis_block['genesis_stakeholders']:
                if self.my_profile.address == peers['address']:
                    self.can_vote = True

        if self.is_first_node:
            self.can_vote = True

        if self.can_vote:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            future = asyncio.ensure_future(self.run_broadcast_new_commitment(last_genesis_block))
            loop.run_until_complete(future)

    def reveal_phase(self, scheduler):
        slot, seconds_till_the_next_slot = self.get_current_slot()

        dd = datetime.now() + timedelta(seconds=(7 - slot + 2) * 5 + seconds_till_the_next_slot)

        scheduler.add_job(self.reveal_phase, 'date', run_date=dd,
                          kwargs={'scheduler': scheduler})

        opn = {
            'public_key': self.my_profile.public_key,
            'opening': self.my_opening
        }
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(self.run_broadcast_new_opening(opn))
        loop.run_until_complete(future)

    def create_secret_seed(self, scheduler):
        slot, seconds_till_the_next_slot = self.get_current_slot()

        dd = datetime.now() + timedelta(seconds=(7 - slot + 4) * 5 + seconds_till_the_next_slot)

        scheduler.add_job(self.create_secret_seed, 'date', run_date=dd,
                          kwargs={'scheduler': scheduler})
        if self.can_vote:
            seed = base64.b64decode(self.my_opening.encode())
            for comt in self.commitments:
                for opn in self.openings:
                    if BlockChain.__validate_commitment(opening=opn, commitment=comt):
                        seed = BlockChain.xor(base64.b64decode(opn['opening'].encode()), seed)
            self.seed = base64.b64encode(seed).decode('utf-8')

            epoch = self.get_current_epoch()[0]
            slot = self.get_current_slot()[0]
            self.my_seeds[epoch] = copy.deepcopy(self.seed)

            write_seed_to_file = {
                'epoch': epoch,
                'slot': slot,
                'seed': self.seed
            }
            self.last_seed['epoch'] = epoch
            self.last_seed['seed'] = epoch
            FileModule.append_secrets_to_file(self.my_profile.address.split(':')[2].split('/')[0], write_seed_to_file)

        self.can_vote = False
        self.openings.clear()
        self.commitments.clear()

    def add_commitment(self, public_key, commitment):
        slot, seconds_till_the_next_slot = self.get_current_slot()
        if slot < 2:
            cmt = {
                'public_key': public_key,
                'commitment': commitment
            }
            self.commitments.append(cmt)

    def add_opening(self, public_key, opening):
        slot, seconds_till_the_next_slot = self.get_current_slot()
        if slot in [2, 3]:
            opn = {
                'public_key':public_key,
                'opening':opening
            }
            self.openings.append(opn)

    def get_openings(self):
        all_openings = self.openings
        all_openings.append(self.my_opening)
        return all_openings

    def get_commitments(self):
        all_commitments = self.commitments
        all_commitments.append(self.my_commitment)
        return all_commitments

    def get_amount(self, public_key):
        amount = 0
        chain = copy.deepcopy(self.chain)
        transactions = copy.deepcopy(self.transactions)
        outputs = {}
        for i in range(len(chain)):
            if chain[i]['block_type'] != 'genesis':
                for transaction in chain[i]['transactions']:
                    for j in range(len(transaction['outputs'])):
                        if transaction['outputs'][j]['public_key'] == public_key:
                            outputs[transaction['hash']+str(j)] = {
                                'transaction-hash': transaction['hash'],
                                'id': j,
                                'value': transaction['outputs'][j]['value'],
                                "public_key": public_key
                            }
        for transaction in transactions:
            for j in range(len(transaction['outputs'])):
                if transaction['outputs'][j]['public_key'] == public_key:
                    outputs[transaction['hash'] + str(j)] = {
                        'transaction-hash': transaction['hash'],
                        'id': j,
                        'value': transaction['outputs'][j]['value'],
                        "public_key": public_key
                    }

        for i in range(len(chain)):
            if chain[i]['block_type'] != 'genesis':
                for transaction in chain[i]['transactions']:
                    for j in range(len(transaction['inputs'])):
                        if transaction['inputs'][j]['previous_out']['hash'] + \
                                str(transaction['inputs'][j]['previous_out']['index']) in outputs:
                            del outputs[transaction['inputs'][j]['previous_out']['hash']
                                        + str(transaction['inputs'][j]['previous_out']['index'])]

        for transaction in transactions:
            for j in range(len(transaction['inputs'])):
                if transaction['inputs'][j]['previous_out']['hash'] + \
                        str(transaction['inputs'][j]['previous_out']['index']) in outputs:
                    del outputs[transaction['inputs'][j]['previous_out']['hash']
                                + str(transaction['inputs'][j]['previous_out']['index'])]

        for key in outputs:
            amount = amount + outputs[key]['value']

        return amount, outputs

    def get_amount_genesis_stakeholders(self, wallets):
        chain = copy.deepcopy(self.chain)
        outputs = {}
        for i in range(len(chain)):
            if chain[i]['block_type'] != 'genesis':
                for transaction in chain[i]['transactions']:
                    for j in range(len(transaction['outputs'])):
                        if transaction['outputs'][j]['public_key'] in wallets:
                            outputs[transaction['hash'] + str(j)] = {
                                'transaction-hash': transaction['hash'],
                                'id': j,
                                'value': transaction['outputs'][j]['value'],
                                "public_key": transaction['outputs'][j]['public_key']
                            }

        for i in range(len(chain)):
            if chain[i]['block_type'] != 'genesis':
                for transaction in chain[i]['transactions']:
                    for j in range(len(transaction['inputs'])):
                        if transaction['inputs'][j]['previous_out']['hash'] + \
                                str(transaction['inputs'][j]['previous_out']['index']) in outputs:
                            del outputs[transaction['inputs'][j]['previous_out']['hash']
                                        + str(transaction['inputs'][j]['previous_out']['index'])]

        for key in outputs:
            wallets[outputs[key]['public_key']] = wallets[outputs[key]['public_key']] + outputs[key]['value']
        return wallets

    def get_public_key(self):
        return self.my_profile['public_key']

    def is_slot_leader(self, address):
        slot = self.get_current_slot()[0]
        genesis_block = self.last_genesis_block()
        if genesis_block['slot_leaders'][slot]['address'] == address:
            return True
        return False

    def start_mining(self, scheduler, private_key):
        BlockChain.build_new_blocks(self, scheduler, private_key)
        BlockChain.run_election_process(self, scheduler, private_key)
        scheduler.start()
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()

    def update_chain(self, new_chain, rollback_index):
        if rollback_index > 0:
            for i in range(rollback_index, len(self.chain)):
                for j in range(len(self.chain[i]['transactions'])):
                    self.transactions.append(self.chain[i]['transactions'][j])

        last_genesis_block = self.last_genesis_block()
        if last_genesis_block is not None:
            for stakeholder in last_genesis_block['genesis_stakeholders']:
                self.peers.add(Stakeholder.Stakeholder(stakeholder['public_key'], stakeholder['address']))

        self.chain = new_chain

    async def run_broadcast_new_genesis_block(self, genesis_block):

        tasks = []
        # Fetch all responses within one Client session,
        # keep connection alive for all requests.
        viz_addresses = {}
        async with ClientSession() as session:
            for index in range(len(genesis_block['slot_leaders'])):
                if genesis_block['slot_leaders'][index]['address'] != self.my_profile.address and \
                                genesis_block['slot_leaders'][index]['address'] not in viz_addresses:
                    viz_addresses[genesis_block['slot_leaders'][index]['address']] = 1
                    broadcast_new_block = {
                        'length': len(self.chain),
                        'address': self.my_profile.address
                    }
                    url = genesis_block['slot_leaders'][index]['address'] + 'accept_new_block'
                    task = asyncio.ensure_future(fetch_post_text(url, session, json.dumps(broadcast_new_block)))
                    tasks.append(task)

            responses = await asyncio.gather(*tasks)

    async def run_broadcast_new_epoch_block(self, genesis_block):

        tasks = []
        # Fetch all responses within one Client session,
        # keep connection alive for all requests.
        slot = self.chain[-1]['slot']
        viz_addresses = {}
        async with ClientSession() as session:
            for index in range(slot, len(genesis_block['slot_leaders'])):
                if genesis_block['slot_leaders'][index]['address'] != self.my_profile.address and \
                                genesis_block['slot_leaders'][index]['address'] not in viz_addresses:
                    viz_addresses[genesis_block['slot_leaders'][index]['address']] = 1
                    broadcast_new_block = {
                        'length': len(self.chain),
                        'address': self.my_profile.address
                    }
                    url = genesis_block['slot_leaders'][index]['address'] + 'accept_new_block'
                    task = asyncio.ensure_future(fetch_post_text(url, session, json.dumps(broadcast_new_block)))
                    tasks.append(task)
            await asyncio.gather(*tasks)

    async def run_broadcast_new_transaction(self, transaction):

        tasks = []
        async with ClientSession() as session:
            for peer in self.peers:
                if peer.address != self.my_profile.address:
                    url = peer.address + 'transactions/broadcast'
                    task = asyncio.ensure_future(fetch_post_text(url, session, json.dumps(transaction)))
                    tasks.append(task)

            for peer in self.pending_peers:
                if peer.address != self.my_profile.address:
                    url = peer.address + 'transactions/broadcast'
                    task = asyncio.ensure_future(fetch_post_text(url, session, json.dumps(transaction)))
                    tasks.append(task)

            await asyncio.gather(*tasks)

    async def run_broadcast_new_commitment(self, last_genesis_block):
        tasks = []
        async with ClientSession() as session:
            for peers in last_genesis_block['genesis_stakeholders']:
                if self.my_profile.address != peers['address']:
                    url = peers['address'] + 'commitment'
                    task = asyncio.ensure_future(fetch_post_json(url, session, json.dumps(self.my_commitment),
                                                                 expected_status=201))
                    tasks.append(task)

            responses = await asyncio.gather(*tasks)

            for response in responses:
                self.peers_for_reveal.append(response['address'])

    async def run_broadcast_new_opening(self, opening):
        tasks = []
        async with ClientSession() as session:
            for node in self.peers_for_reveal:
                if self.my_profile.address != node:
                    url = node + 'opening'
                    task = asyncio.ensure_future(fetch_post_text(url, session, json.dumps(opening)))
                    tasks.append(task)
            await asyncio.gather(*tasks)
            self.peers_for_reveal = []

    async def run_consensus_algorithm(self):
        tasks = []
        async with ClientSession() as session:
            for node in self.peers:
                if self.my_profile.address != node.address:
                    url = node.address + 'chain_length'
                    task = asyncio.ensure_future(fetch_get_json(url, session, 200))
                    tasks.append(task)

            responses = await asyncio.gather(*tasks)
            new_responses = sorted(responses, key=lambda k: k['length'], reverse=True)
            """
            if len(new_responses) > 1:
                print(str(new_responses[0]['length']) + ' ' + str(new_responses[1]['length']))
            else:
                print(str(new_responses[0]['length']))
            """
            tasks = []
            index = 0
            while index < len(new_responses):
                i = 0
                while i < 5:
                    if new_responses[index]['length'] < len(self.chain):
                        return False
                    if i < len(new_responses):
                        url = new_responses[index]['address'] + 'chain'
                        task = asyncio.ensure_future(fetch_get_json(url, session, 200))
                        tasks.append(task)
                    i = i + 1
                responses = await asyncio.gather(*tasks)
                new_chains = sorted(responses, key=lambda k: k['length'], reverse=True)
                for chain in new_chains:
                    result, rollback_index = self.verify_block_chain(chain['chain'])
                    #verify incoming transactions
                    if result:
                        result2 = self.verify_transactions_in_consensus_algorithm(rollback_index, chain['chain'])
                        if result2:
                            self.update_chain(chain['chain'], rollback_index)
                            return True

                index = index + i

    @staticmethod
    def build_new_blocks(block_chain, scheduler, private_key):
        slot, seconds_till_the_next_slot = block_chain.get_current_slot()
        dd = datetime.now() + timedelta(seconds=seconds_till_the_next_slot) + timedelta(milliseconds=100)
        scheduler.add_job(BlockChain.build_new_blocks, 'date', run_date=dd, name=block_chain.my_profile.address,
                          kwargs={'scheduler': scheduler, 'block_chain': block_chain, 'private_key': private_key})

        genesis_block = block_chain.last_genesis_block()
        epoch, seconds = block_chain.get_current_epoch()

        if genesis_block['block_type'] == "first-genesis":
            if block_chain.is_first_node:
                if slot < 6:
                    block_chain.forge_new_block(private_key)
                else:
                    block_chain.new_genesis_block(private_key)
        else:
            if genesis_block['slot_leaders'][slot]['public_key'] == block_chain.my_profile.public_key and\
                            genesis_block['slot_leaders'][slot]['address'] == block_chain.my_profile.address:
                if slot < 6:
                    block_chain.forge_new_block(private_key)
                else:
                    if genesis_block['epoch'] < epoch+1:
                        block_chain.new_genesis_block(private_key)

    @staticmethod
    def run_election_process(block_chain, scheduler, private_key):
        slot, seconds_till_the_next_slot = block_chain.get_current_slot()
        if slot < 2:
            block_chain.commitment_phase(private_key, scheduler)

            dd = datetime.now() + timedelta(seconds=(2-slot-1)*5 + seconds_till_the_next_slot) + timedelta(milliseconds=100)

            scheduler.add_job(block_chain.reveal_phase, 'date', run_date=dd,
                              kwargs={'scheduler': scheduler})

            dd = datetime.now() + timedelta(seconds=(4-slot-1)*5 + seconds_till_the_next_slot) + timedelta(milliseconds=100)

            scheduler.add_job(block_chain.create_secret_seed, 'date', run_date=dd,
                              kwargs={'scheduler': scheduler})
        else:
            dd = datetime.now() + timedelta(seconds=(7-slot) * 5 + seconds_till_the_next_slot + 0.1)

            scheduler.add_job(BlockChain.run_election_process, 'date', run_date=dd,
                              kwargs={'scheduler': scheduler, 'block_chain': block_chain, 'private_key': private_key})

    @staticmethod
    def __validate_commitment(opening, commitment):
        if opening['public_key'] != commitment['public_key']:
            return False
        # Step2: Validate the signing
        if not EcdsaSigning.verify_sign(opening['public_key'], commitment['commitment'], opening['opening']):
            return False
        return True

    @staticmethod
    def xor(var, key):
        return bytes(a ^ b for a, b in zip(var, key))

    @staticmethod
    def generate_new_wallet():
        private_key, public_key = EcdsaSigning.generate_keys()
        wallet = {
            "private_key": private_key,
            "public_key": public_key
        }
        return wallet

    @staticmethod
    def verify_transaction(new_chain, transaction, transactions):
        # Step1:  check if transaction already exist
        chain = copy.deepcopy(new_chain)
        inputs_len = len(transaction['inputs'])
        amount = 0
        for i in range(len(chain)):
            if chain[i]['block_type'] != 'genesis':
                for trans in chain[i]['transactions']:
                    if trans['hash'] == transaction['hash']:
                        return False, 'Transaction already exist'
                    for existing_inputs in trans['inputs']:
                        for input in transaction['inputs']:
                            if existing_inputs['previous_out']['hash'] == input['previous_out']['hash'] and \
                                            existing_inputs['previous_out']['index'] == input['previous_out']['index']:
                                return False, 'Invalid transaction'

                    # Step2: check signature for every input
                    for input in transaction['inputs']:
                        if input['previous_out']['hash'] == trans['hash']:
                            if not EcdsaSigning.verify_sign(
                                    trans['outputs'][input['previous_out']['index']]['public_key'], input['signature'],
                                    json.dumps(input['previous_out'])):
                                return False, 'Invalid signature'
                            else:
                                amount = amount + trans['outputs'][input['previous_out']['index']]['value']
                                inputs_len = inputs_len - 1

        for trans in transactions:
            if trans['hash'] == transaction['hash']:
                return False, 'Transaction already exist'

            for existing_inputs in trans['inputs']:
                for input in transaction['inputs']:
                    if existing_inputs['previous_out']['hash'] == input['previous_out']['hash'] and \
                                    existing_inputs['previous_out']['index'] == input['previous_out']['index']:
                        return False, 'Invalid transaction'

            # Step2: check signature for every input
            for input in transaction['inputs']:
                if input['previous_out']['hash'] == trans['hash']:
                    if not EcdsaSigning.verify_sign(
                            trans['outputs'][input['previous_out']['index']]['public_key'],
                            input['signature'],
                            json.dumps(input['previous_out'])):
                        return False, 'Invalid signature'
                    else:
                        amount = amount + trans['outputs'][input['previous_out']['index']]['value']
                        inputs_len = inputs_len - 1

        # Step3: D check if input are point to valid transactions
        if inputs_len > 0:
            return False, 'Inputs are not point to valid outputs'

        # Step4:
        amount_in_new_trans = 0
        for output in transaction['outputs']:
            amount_in_new_trans = amount_in_new_trans + output['value']

        if amount_in_new_trans + MIN_FEES > amount:
            return False, 'Invalid transaction',

        fees = amount - amount_in_new_trans

        return True, 'Transaction accepted', fees


async def fetch_get_json(url, session, expected_status=200):
    async with session.get(url=url, headers=headers) as response:
        if response.status == expected_status:
            return await response.json()


async def fetch_post_json(url, session, body, expected_status=200):
    async with session.post(url=url, data=body, headers=headers) as response:
        if response.status == expected_status:
            return await response.json()


async def fetch_post_text(url, session, body, expected_status=200):
    async with session.post(url=url, data=body, headers=headers) as response:
        if response.status == expected_status:
            return await response.read()

