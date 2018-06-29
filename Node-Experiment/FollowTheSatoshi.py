import random
import math
import hashlib
import base64


class Node(object):
    def __init__(self, left=None, right=None, stakeholder=None, hash=None):
        self.left = left
        self.right = right
        self.stakeholder = stakeholder
        if hash is None:
            self.hash = stakeholder.get_hash()
        else:
            self.hash = hash

    def get_coins(self):
        if self.stakeholder is not None:
            return self.stakeholder.coins
        else:
            return self.right.get_coins() + self.left.get_coins()


def generate_merkle_tree(stakeholders, seed):
    merkle_tree = list()
    stakeholders_with_positive_amount = list()

    for item in stakeholders:
        if item.coins > 0:
            stakeholders_with_positive_amount.append(item)

    random.seed(seed)
    random.shuffle(stakeholders_with_positive_amount)
    sh_len = len(stakeholders_with_positive_amount)

    for i in range(sh_len):
        merkle_tree.append(Node(stakeholder=stakeholders_with_positive_amount[i]))

    index = 0
    len_merkle = len(merkle_tree)
    i = 0
    while i < len_merkle-1:
        left = merkle_tree[index]
        right = merkle_tree[index+1]
        hash_content = left.hash+right.hash+str(left.get_coins())+str(right.get_coins())
        hash = hashlib.sha256(base64.b64encode(hash_content.encode('utf-8'))).hexdigest()
        merkle_tree.append(Node(left=left, right=right, hash=hash))
        index += 2
        i += 1
    return merkle_tree


def pick_random_stake_holder(markle_tree, seed):

    node = markle_tree[len(markle_tree)-1]
    random.seed(seed)
    while True:
        if node.stakeholder is not None:
            return node.stakeholder
        left_coins_balance = node.left.get_coins()
        right_coins_balance = node.right.get_coins()
        rnd = random.randint(0, math.ceil(left_coins_balance+right_coins_balance))
        if rnd <= left_coins_balance:
            node = node.left
        else:
            node = node.right
