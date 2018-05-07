import random

reward = 0.1

class StackHolder(object):
    def __init__(self, id, stack):
        self.id=id
        self.stack=stack


def create_users():
    userList = list()
    for i in range(1000):
        stackHolder = StackHolder(i, random.randint(1,1000))
        userList.append(stackHolder)
    return userList

def generate_genesis_block(users):
    stackHoldersList = list()
    totalStack = 0
    i=0
    while i<100:
        index = random.randint(0, len(users)-1)
        if users[index].stack >=0:
            stackHoldersList.append(users[index])
            totalStack = totalStack + users[index].stack
            del users[index]
            i=i+1
        else:
            i=i-1
    genesisBlock = list()
    probabilityMax = 0
    for stackHolder in stackHoldersList:
        if(stackHolder.stack/totalStack>probabilityMax):
            probabilityMax = stackHolder.stack/totalStack
        genesisBlock.append({
            'stackHolder' : stackHolder,
            'p' : stackHolder.stack/totalStack
        })
    return genesisBlock, probabilityMax

def generate_first_slot_leaders(genesisbBlock,slots_number, probabilityMax):
    slotLeaders = list()
    for i in range(slots_number):
        elected = False
        while not elected:
            for i in range(len(genesisbBlock)):
                if flip(genesisbBlock[i]["p"], probabilityMax):
                    slotLeaders.append({
                        'id':i,
                        "slotLeader": genesisbBlock[i]["stackHolder"]
                    })
                    elected=True
                    del genesisbBlock[i]
                    break
    return slotLeaders


def get_honest_users(genesisBlock):
    new_list = sorted(genesisBlock, key=lambda user: user['stackHolder'].stack,reverse=True)
    richest_users = list()
    for i in range(15):
        richest_users.append(new_list[i]['stackHolder'])
    return richest_users


def destroy_genesis_block(users, genesisblock):
    for i in range(len(genesisblock)):
        users.append(genesisblock[i]['stackHolder'])
    del genesisblock[:]

def move_slots_to_genesis_block(slot_leaders, genesisBlock):
    for i in range(len(slot_leaders)):
        genesisBlock.append({
            'stackHolder': StackHolder(slot_leaders[i]['slotLeader'].id,slot_leaders[i]['slotLeader'].stack),
            'p': 1
        })
    del slot_leaders[:]

def flip(p, p_max):
    return True if random.uniform(0,p_max) < p else False


def election(genesisBlock, first_15_percent, slot_numbers, probability_max):
    slotLeaders = list()
    for i in range (slot_numbers):
        votes = dict()
        elected = False
        while not elected:
            for j in range(len(first_15_percent)):
                for k in range(len(genesisBlock)):
                    if flip(genesisBlock[k]["p"], probability_max):
                        if k in votes:
                            votes[k] = votes[k] + 1
                        else:
                            votes[k]=1
            #count the votes
            winners = list()
            max_val = 0
            for key in votes:
                if votes[key]>max_val:
                    del winners[:]
                    max_val=votes[key]
                    winners.append(key)
                elif votes[key] == max_val:
                    winners.append(key)
            #It's a draw, choose again
            if len(winners)>1:
                elected = False
            else:
                elected = True
                slotLeaders.append({
                    'id': i,
                    "slotLeader": genesisBlock[winners[0]]["stackHolder"]
                })
                del genesisBlock[winners[0]]
            del winners[:]
    return slotLeaders

def get_user_index(users,usr_id):
    for index in range(len(users)):
        if users[index].id == usr_id:
            return index
    return -1