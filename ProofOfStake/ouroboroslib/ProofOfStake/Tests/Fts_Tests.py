from random import randint
from FollowTheSatoshi import pick_random_stake_holder, generate_merkle_tree

from Stakeholder import GenesisStakeholder

## genera 100 Stakeholders

stakeholders = list()
seed = 'cosminasda'

for i in range(5):
    stakeholders.append(GenesisStakeholder(coins=randint(1, 1000), public_key=i, address=0))

merkle_tree = generate_merkle_tree(stakeholders, seed)

stakeholder1, merk = pick_random_stake_holder(merkle_tree, seed)

print(merk)

"""
stakeholder2 = pick_random_stake_holder(merkle_tree, seed)
stakeholder3 = pick_random_stake_holder(merkle_tree, seed)
stakeholder4 = pick_random_stake_holder(merkle_tree, seed)
stakeholder5 = pick_random_stake_holder(merkle_tree, seed)

score = {}

for i in range(1000):
    stk = pick_random_stake_holder(merkle_tree, seed + str(i))
    if stk.public_key in score:
        score[stk.public_key] = score[stk.public_key] + 1
    else:
        score[stk.public_key] = 1

for stake in stakeholders:
    print('pk- ' + str(stake.public_key) + ' coins- ' + str(stake.coins) + ' score- ' + str(score[stake.public_key]))


"""