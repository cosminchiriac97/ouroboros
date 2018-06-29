
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
        self.my_profile = my_profile
        self.my_private_key = my_private_key
        self.commitments = []
        self.my_commitment = {}
        self.broadcasted_commitments = {}
        self.openings = []
        self.my_opening = None
        self.broadcasted_openings = {}
        self.seed = None
        self.my_seeds = {}
        self.is_first_node = is_first_node
        if is_first_node:
            self.generate_first_genesis_block()
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

        transaction_len = len(self.transactions)
        checked_transactions =[]
        i = 0
        while i < transaction_len:
            trans = self.transactions[i]
            result = BlockChain.verify_transaction(self.chain, trans, checked_transactions)
            if result[0]:
                transactions_for_forge.append(trans)
                fees_values = fees_values + result[2]
            checked_transactions.append(copy.deepcopy(trans))
            i = i + 1
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
            'public_key': self.my_profile.public_key,
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
            'address': self.my_profile.address,
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
        future = asyncio.ensure_future(self.run_broadcast_new_genesis_block(genesis_block, last_genesis_block ))
        loop.run_until_complete(future)

        return genesis_block

    def get_current_epoch(self):
        d1 = parser.parse(self.chain[0]['start_date'])
        d2 = datetime.now()
        seconds = (d2-d1).total_seconds()
        current_epoch = int(seconds/80)
        seconds_till_the_next_epoch = (current_epoch+1)*80 - (d2-d1).total_seconds()
        return current_epoch, seconds_till_the_next_epoch

    def get_current_slot(self):
        d1 = parser.parse(self.chain[0]['start_date'])
        d2 = datetime.now()
        seconds = (d2 - d1).total_seconds()
        current_epoch = int(seconds / 80)
        current_slot = int((d2-d1).total_seconds()-current_epoch*80)/10
        seconds_till_the_next_slot = current_epoch*80 + ((int(current_slot)+1)*10) - (d2-d1).total_seconds()
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
            print('len')
            return False, -1

        epoch = self.get_current_epoch()[0]
        slot = self.get_current_slot()[0]
        if len(block_chain) > epoch*7 + slot+2:
            print('slot')
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

        if len(self.chain) - index_for_rollback > 20:
            return False, -1

        last_genesis = self.last_genesis_block()
        if last_genesis['block_type'] == 'first-genesis':
            last_genesis = None
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

            if last_genesis is not None:
                if block_chain[index]['address'] != last_genesis['slot_leaders'][block_chain[index]['slot']]['address']:
                    print('block - genesis')
                    return False, -1

            # verify seeds and slot leaders

            if block_chain[index]['block_type'] == 'genesis':
                for i in range(index-1, 1, -1):
                    if block_chain[i]['block_type'] == 'genesis':
                        if block_chain[index]['epoch'] == block_chain[i]['epoch']:
                            print('trimite fraierul aici block gresit ' +  block_chain[i]['address'])
                            return False, -1

                if block_chain[index]['epoch'] in self.my_seeds:
                    if self.my_seeds[block_chain[index]['epoch']] != block_chain[index]['seed']:
                        print('se futu seed-ul')
                        return False, -1

                if last_genesis is not None:
                    list_stakeholders = list()
                    for stakeholder in last_genesis['genesis_stakeholders']:
                        list_stakeholders.append(
                            Stakeholder.GenesisStakeholder(stakeholder['coins'], stakeholder['public_key'],
                                                           stakeholder['address']))

                    markle_tree = FollowTheSatoshi.generate_merkle_tree(list_stakeholders, last_genesis['seed'])
                    slot_leaders = list()

                    for i in range(8):
                        slot_leader = FollowTheSatoshi.pick_random_stake_holder(markle_tree,
                                                                                last_genesis['seed'] + str(i))

                        slot_leaders.append({
                            'coins': slot_leader.coins,
                            'public_key': slot_leader.public_key,
                            'address': slot_leader.address
                        })

                    if len(slot_leaders) != len(block_chain[index]['slot_leaders']):
                        print('putin probabil')
                        return False, -1

                    for j in range(len(slot_leaders)):
                        if slot_leaders[j]['address'] != block_chain[index]['slot_leaders'][j]['address'] or \
                                        slot_leaders[j]['coins'] != block_chain[index]['slot_leaders'][j]['coins']:
                            print('aici oare')
                            return False, -1

                last_genesis = copy.deepcopy(block_chain[index])

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
        dd = datetime.now() + timedelta(seconds=(7-slot) * 10 + seconds_till_the_next_slot)
        scheduler.add_job(self.commitment_phase, 'date', run_date=dd,
                          kwargs={'private_key': private_key, 'scheduler': scheduler})
        byte_array = b"\x00" + secrets.token_bytes(8) + b"\x00"
        self.my_opening = base64.b64encode(byte_array).decode('utf-8')
        commitment = EcdsaSigning.sign_data(private_key, self.my_opening)
        self.my_commitment = {
            'public_key': self.my_profile.public_key,
            'commitment': commitment,
            'address': self.my_profile.address
        }
        self.consensus_algorithm()
        time.sleep(2)
        last_genesis_block = self.last_genesis_block()
        if last_genesis_block['block_type'] == 'genesis':
            for peers in last_genesis_block['genesis_stakeholders']:
                if self.my_profile.address == peers['address']:
                    self.can_vote = True

        if self.is_first_node:
            self.can_vote = True

        if self.can_vote:
            time_for_sleep = random.randint(0, 4)
            time.sleep(time_for_sleep)
            self.run_broadcast_new_commitment(last_genesis_block, self.my_commitment, self.my_profile.address)

    def reveal_phase(self, scheduler):
        slot, seconds_till_the_next_slot = self.get_current_slot()
        print(str(slot) + ' ' + str(seconds_till_the_next_slot))

        dd = datetime.now() + timedelta(seconds=(7 - slot + 2) * 10 + seconds_till_the_next_slot)

        scheduler.add_job(self.reveal_phase, 'date', run_date=dd,
                          kwargs={'scheduler': scheduler})

        opn = {
            'public_key': self.my_profile.public_key,
            'opening': self.my_opening,
            'address': self.my_profile.address
        }
        last_genesis_block = self.last_genesis_block()
        if self.can_vote:
            time_for_sleep = random.randint(0, 4)
            time.sleep(time_for_sleep)
            self.run_broadcast_new_opening(last_genesis_block, opn, self.my_profile.address)

    def create_secret_seed(self, scheduler):
        slot, seconds_till_the_next_slot = self.get_current_slot()

        dd = datetime.now() + timedelta(seconds=(7 - slot + 4) * 10 + seconds_till_the_next_slot)

        scheduler.add_job(self.create_secret_seed, 'date', run_date=dd,
                          kwargs={'scheduler': scheduler})
        addresses = {}
        lst_gen = self.last_genesis_block()
        if self.can_vote:
            seed = base64.b64decode(self.my_opening.encode())
            sorted_commitments = sorted(self.commitments, key=lambda k: k['commitment'])
            for comt in sorted_commitments:
                for opn in self.openings:
                    if BlockChain.__validate_commitment(opening=opn, commitment=comt):
                        address = BlockChain.get_address_by_public_key(lst_gen, opn['public_key'])
                        if address not in addresses:
                            addresses[address] = base64.b64decode(opn['opening'].encode())
                            seed = BlockChain.xor(base64.b64decode(opn['opening'].encode()), seed)
            self.seed = base64.b64encode(seed).decode('utf-8')
            epoch = self.get_current_epoch()[0]
            slot = self.get_current_slot()[0]
            self.my_seeds[epoch+1] = copy.deepcopy(self.seed)

            write_seed_to_file = {
                'epoch': epoch,
                'slot': slot,
                'seed': self.seed,
                'openings': addresses
            }
            FileModule.append_secrets_to_file(self.my_profile.address.split(':')[2].split('/')[0], write_seed_to_file)

        self.can_vote = False
        self.broadcasted_openings = {}
        self.broadcasted_commitments = {}
        self.openings.clear()
        self.commitments.clear()

    def add_commitment(self, public_key, commitment, address):
        slot, seconds_till_the_next_slot = self.get_current_slot()
        last_genesis_block = self.last_genesis_block()

        can_vote = False
        valid_public_key = False

        if last_genesis_block['block_type'] == 'genesis':
            for peers in last_genesis_block['genesis_stakeholders']:
                if address == peers['address']:
                    can_vote = True
                if public_key == peers['public_key']:
                    valid_public_key = True

        if slot < 2 and can_vote and valid_public_key and commitment+public_key not in self.broadcasted_commitments:

            cmt = {
                'public_key': public_key,
                'commitment': commitment,
                'address': address
            }

            commitment_to_broadcast = {
                'public_key': public_key,
                'commitment': commitment,
                'address': self.my_profile.address
            }

            self.broadcasted_commitments[commitment+public_key] = 1
            self.commitments.append(cmt)
            self.run_broadcast_new_commitment(last_genesis_block, commitment_to_broadcast, address)

    def add_opening(self, public_key, opening, address):
        slot, seconds_till_the_next_slot = self.get_current_slot()
        last_genesis_block = self.last_genesis_block()
        can_vote = False
        valid_public_key = False
        if last_genesis_block['block_type'] == 'genesis':
            for peers in last_genesis_block['genesis_stakeholders']:
                if address == peers['address']:
                    can_vote = True
                if public_key == peers['public_key']:
                    valid_public_key = True

        if slot in [2, 3] and can_vote and valid_public_key and opening+public_key not in self.broadcasted_openings:
            opn = {
                'public_key': public_key,
                'opening': opening,
                'address': address
            }

            opening_to_broadcast = {
                'public_key': public_key,
                'opening': opening,
                'address': self.my_profile.address
            }
            self.broadcasted_openings[opening+public_key] = 1
            self.openings.append(opn)
            self.run_broadcast_new_opening(last_genesis_block, opening_to_broadcast, address)

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
        return self.my_profile.public_key

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

    async def run_broadcast_new_genesis_block(self, genesis_block, last_genesis):

        tasks = []
        # Fetch all responses within one Client session,
        # keep connection alive for all requests.
        viz_addresses = {}
        slot = self.get_current_slot()[0]
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

            if last_genesis['block_type'] == 'genesis':
                for index in range(slot+1, len(last_genesis['slot_leaders'])):
                    if last_genesis['slot_leaders'][index]['address'] != self.my_profile.address and \
                                    last_genesis['slot_leaders'][index]['address'] not in viz_addresses:
                        viz_addresses[last_genesis['slot_leaders'][index]['address']] = 1
                        broadcast_new_block = {
                            'length': len(self.chain),
                            'address': self.my_profile.address
                        }
                        url = last_genesis['slot_leaders'][index]['address'] + 'accept_new_block'
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

    def run_broadcast_new_commitment(self, last_genesis_block, commitment, sender_address):
        urls = []
        for peers in last_genesis_block['genesis_stakeholders']:
            if self.my_profile.address != peers['address'] and peers['address'] != sender_address:
                urls.append(peers['address'] + 'commitment')
        if len(urls) != 0:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tasks = []
            for url in urls:
                task = asyncio.ensure_future(post_text(url, json.dumps(commitment)))
                tasks.append(task)
            loop.run_until_complete(asyncio.wait(tasks, timeout=3))

    def run_broadcast_new_opening(self, last_genesis_block, opening, sender_address):
        urls = []
        for peers in last_genesis_block['genesis_stakeholders']:
            if self.my_profile.address != peers['address'] and peers['address'] != sender_address:
                urls.append(peers['address'] + 'opening')
        if len(urls) != 0:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tasks = []
            for url in urls:
                task = asyncio.ensure_future(post_text(url, json.dumps(opening)))
                tasks.append(task)
            loop.run_until_complete(asyncio.wait(tasks, timeout=3))

    async def run_consensus_algorithm(self):
        tasks = []
        async with ClientSession() as session:
            for node in self.peers:
                if self.my_profile.address != node.address:
                    url = node.address + 'chain_length'
                    task = asyncio.ensure_future(fetch_get_json(url, session, 200))
                    tasks.append(task)

            responses = await asyncio.gather(*tasks)
            responses = filter(None, responses)
            new_responses = sorted(responses, key=lambda k: k['length'], reverse=True)
            tasks = []
            index = 0
            while index < len(new_responses):
                i = 0
                epoch = self.get_current_epoch()[0]
                slot = self.get_current_slot()[0]
                while i < 5:
                    if new_responses[index]['length'] < len(self.chain):
                        return False
                    if i < len(new_responses) and new_responses[index]['length'] <= epoch*7 + slot+2:
                        url = new_responses[index]['address'] + 'chain'
                        task = asyncio.ensure_future(fetch_get_json(url, session, 200))
                        tasks.append(task)
                    i = i + 1
                responses = await asyncio.gather(*tasks)
                new_chains = sorted(responses, key=lambda k: k['length'], reverse=True)
                for chain in new_chains:
                    result, rollback_index = self.verify_block_chain(chain['chain'])
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
        if slot == 0 and seconds_till_the_next_slot > 5:

            dd = datetime.now() + timedelta(seconds=0.5) + timedelta(
                milliseconds=100)

            scheduler.add_job(block_chain.commitment_phase, 'date', run_date=dd,
                              kwargs={'private_key': private_key, 'scheduler': scheduler})

            dd = datetime.now() + timedelta(seconds=(2-slot-1)*10 + seconds_till_the_next_slot) + timedelta(milliseconds=100)

            scheduler.add_job(block_chain.reveal_phase, 'date', run_date=dd,
                              kwargs={'scheduler': scheduler})

            dd = datetime.now() + timedelta(seconds=(4-slot-1)*10 + seconds_till_the_next_slot) + timedelta(milliseconds=100)

            scheduler.add_job(block_chain.create_secret_seed, 'date', run_date=dd,
                              kwargs={'scheduler': scheduler})
        else:
            dd = datetime.now() + timedelta(seconds=(7-slot) * 10 + seconds_till_the_next_slot + 0.1)

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

    @staticmethod
    def get_address_by_public_key(last_genesis, public_key):
        for stakeholder in last_genesis['genesis_stakeholders']:
            if stakeholder['public_key'] == public_key:
                return stakeholder['address']


async def fetch_get_json(url, session, expected_status=200):
    try:
        async with session.get(url=url, headers=headers) as response:
            if response.status == expected_status:
                return await response.json()
    except Exception:
        pass


async def fetch_post_json(url, session, body, expected_status=200):
    try:
        async with session.post(url=url, data=body, headers=headers) as response:
            if response.status == expected_status:
                return await response.json()
    except Exception:
        pass


async def fetch_post_text(url, session, body, expected_status=200):
    try:
        async with session.post(url=url, data=body, headers=headers) as response:
            if response.status == expected_status:
                return await response.read()
    except Exception:
        pass


async def post_json(url, body):
    async with ClientSession() as session:
        async with session.post(url=url, data=body, headers=headers) as response:
            await response.json()


async def post_text(url, body):
    async with ClientSession() as session:
        async with session.post(url=url, data=body, headers=headers) as response:
            await response.read()
