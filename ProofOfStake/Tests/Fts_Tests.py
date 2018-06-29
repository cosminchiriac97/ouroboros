from FollowTheSatoshi import pick_random_stake_holder, generate_merkle_tree
import random
from Stakeholder import GenesisStakeholder

## genera 100 Stakeholders

stakeholders = list()
seed = ''.join(random.choice('zxcvbnmlkjhgfdsaqwertyuioZXCVBNMLKJHGFDSAQWERTYUIOP') for _ in range(8))
init = 500
for i in range(5):
    init = init+50
    stakeholders.append(GenesisStakeholder(coins=init, public_key=i, address=0))

merkle_tree = generate_merkle_tree(stakeholders, seed)

score = {}

for i in range(100):
    stk = pick_random_stake_holder(merkle_tree, seed + str(i))
    if stk.public_key in score:
        score[stk.public_key] = score[stk.public_key] + 1
    else:
        score[stk.public_key] = 1

for stake in stakeholders:
    print('pk- ' + str(stake.public_key) + ' coins- ' + str(stake.coins) + ' score- ' + str(score[stake.public_key]))

