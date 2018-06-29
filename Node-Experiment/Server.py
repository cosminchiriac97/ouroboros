import json, sys, requests, Stakeholder, BlockChain
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from flask import Flask, request, jsonify
from FileModule import init_accounts, append_account, get_account_by_port


import EcdsaSigning

if len(sys.argv) > 1:
    port = int(sys.argv[1])
else:
    port = 5005


app = Flask(__name__)
headers = {'Content-type': 'application/json'}
reference_node = 'http://127.0.0.1:5000'

my_account = get_account_by_port(port)

if my_account is None:
    private_key, public_key = EcdsaSigning.generate_keys()
    account = {
        "private_key": private_key,
        "public_key": public_key,
        "address": "http://127.0.0.1:" + str(port) + "/"
    }
else:
    account = my_account

stakeholder = Stakeholder.Stakeholder(account['public_key'], account['address'])

if port == 5000:
    block_chain = BlockChain.BlockChain(True, stakeholder, account['private_key'])
    init_accounts()
    append_account(account)
else:
    block_chain = BlockChain.BlockChain(False, stakeholder, account['private_key'])
    if my_account is None:
        append_account(account)

data = json.dumps({
    "public_key": stakeholder.public_key,
    "address": stakeholder.address
})

try:
    response = requests.post(reference_node + '/register', data=data, headers=headers)
    if response.status_code == 200:
        try:
            decoded = response.json()
            for x in decoded['nodes']:
                block_chain.register_new_node(x['public_key'], x['address'])
        except (ValueError, KeyError, TypeError):
            print("JSON format error")
    else:
        block_chain.register_new_node(stakeholder.public_key, stakeholder.address)
except:
    block_chain.register_new_node(stakeholder.public_key, stakeholder.address)

if port != 5000:
    try:
        response = requests.get(reference_node + '/chain', headers=headers)
        if response.status_code == 200:
            block_chain.chain = list(response.json()['chain'])
        else:
            sys.exit(0)
    except:
        sys.exit(0)

    block_chain.consensus_algorithm()


@app.route('/register', methods=['POST'])
def register():
    values = request.get_json()
    if values is None:
        return 'Missing content', 400

    required = ['public_key', 'address']

    if not all(k in values for k in required):
        return 'Missing values', 400

    block_chain.register_new_node(values['public_key'], values['address'])

    nodes = block_chain.get_nodes()
    nodes_to_list_dict = list()
    new_node = {
        "public_key": values['public_key'],
        "address": values['address']
    }
    try:
        for node in nodes:
            dict_node = {
                "public_key": node.public_key,
                "address": node.address
            }
            nodes_to_list_dict.append(dict_node)
            if node.address != stakeholder.address and node.address != values['address']:
                requests.post(node.address + 'add_node', data=json.dumps(new_node), headers=headers)
    except Exception as e:
        print('Register: ' + str(e))
    json_data = {
        'nodes': nodes_to_list_dict,
        'length': len(nodes_to_list_dict)
    }
    return jsonify(json_data), 200


@app.route('/wallet/new', methods=['GET'])
def get_new_wallet():
    wallet = BlockChain.BlockChain.generate_new_wallet()
    return jsonify(wallet), 200


@app.route('/nodes', methods=['GET'])
def get_nodes():
    nodes = block_chain.get_nodes()
    nodes_to_list_dict = list()
    for node in nodes:
        nodes_to_list_dict.append(
            {
                "public_key": node.public_key,
                "address": node.address
            }
        )

    data = {
        'nodes': nodes_to_list_dict,
        'length': len(nodes_to_list_dict)
    }
    return jsonify(data), 200


@app.route('/add_node', methods=['POST'])
def add_node():
    values = request.get_json()
    if values is None:
        return 'Missing content', 400

    required = ['public_key', 'address']

    if not all(k in values for k in required):
        return 'Missing values', 400

    block_chain.register_new_node(values['public_key'], values['address'])
    return 'Success', 201


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    if values is None:
        return 'Missing content', 400

    required = ['receiver_public_key', 'amount', 'sender_public_key', 'sender_private_key']

    if not all(k in values for k in required):
        return 'Missing values', 400
    try:
        result, message = block_chain.new_transaction(values)
    except Exception as e:
        print(str(e))
        return str(e), 401

    if result:
        return message, 201
    else:
        return message, 400


@app.route('/transactions/broadcast', methods=['POST'])
def add_transaction_from_internet():
    values = json.loads(request.get_json())

    if values is None:
        return 'Missing content', 400

    required = ['hash', 'size', 'date', 'inputs', 'outputs']

    if not all(k in values for k in required):
        return 'Missing values', 400
    try:
        msg = block_chain.add_transaction_from_internet(values)
        if msg[0]:
            return msg[1], 200
        else:
            return msg[1], 400
    except Exception as e:
        print(e)
        return str(e), 400


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': block_chain.chain,
        'length': len(block_chain.chain),
    }
    return jsonify(response), 200


@app.route('/chain_length', methods=['GET'])
def chain_length():
    response = {
        "length": len(block_chain.chain),
        "address": block_chain.my_profile.address
    }
    return jsonify(response), 200


@app.route('/public_key', methods=['GET'])
def get_public_key():
    json_data = {
        'public_key': block_chain.get_public_key()
    }
    return jsonify(json_data), 200


@app.route('/mine', methods=['POST'])
def mine():
    try:

        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }

        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults)
        block_chain.start_mining(scheduler, block_chain.my_private_key)
    except Exception as e:
        print(str(e))
        return str(e), 400


@app.route('/commitments', methods=['GET'])
def get_commitments():
    return jsonify(block_chain.get_commitments()), 200


@app.route('/commitment', methods=['POST'])
def add_commitments():
    values = request.get_json()
    if values is None:
        return 'Missing content', 400

    required = ['public_key', 'commitment', 'address']
    if not all(k in values for k in required):
        return 'Missing values', 400

    block_chain.add_commitment(values['public_key'], values['commitment'], values['address'])
    return 'Commitment added', 201


@app.route('/opening', methods=['POST'])
def add_openings():
    values = request.get_json()
    if values is None:
        return 'Missing content', 400

    required = ['public_key', 'opening', 'address']
    if not all(k in values for k in required):
        return 'Missing values', 400

    block_chain.add_opening(values['public_key'], values['opening'], values['address'])

    return 'Opening added', 201


@app.route('/openings', methods=['GET'])
def get_openings():
    return jsonify(block_chain.get_openings()), 200


@app.route('/seed', methods=['GET'])
def get_seed():
    return jsonify(str(block_chain.seed)), 200


@app.route('/accept_new_block', methods=['POST'])
def accept_new_block():
    values = request.get_json()
    if values is None:
        return 'Missing content', 400

    required = ['length', 'address']

    if not all(k in values for k in required):
        return 'Missing values', 400
    """
    if not block_chain.is_slot_leader(values['address']):
        return 'You are not the leader of the current slot', 400
    """
    # check block_chain
    if len(block_chain.chain) < values['length']:
        response = requests.get(values['address'] + 'chain', headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            result, index = block_chain.verify_block_chain(response_data['chain'])
            if result:
                result2 = block_chain.verify_transactions_in_consensus_algorithm(index, response_data['chain'])
                if result2:
                    block_chain.update_chain(response_data['chain'], index)
                    return 'Your request has been processed', 200

    return 'Your request has been rejected', 400


app.run(host='127.0.0.1', port=port)
