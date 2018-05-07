from ouroboroslib  import ouroboroslib
import copy
import matplotlib.pyplot as plt
epochs_number = 1000
slots_number = 25
reward = 0.1
def start_mining():
    users = ouroboroslib.create_users()
    copy_of_users = copy.deepcopy(users)
    genesisbBlock, probabilityMax = ouroboroslib.generate_genesis_block(users)
    slotLeaders = ouroboroslib.generate_first_slot_leaders(genesisbBlock, slots_number, 1)
    for i in range(epochs_number):
        for k in range(slots_number):
            #Give rewards to slot leaders
            for j in range(len(slotLeaders)):
                if j==slotLeaders[k]['id']:
                    slotLeaders[k]['slotLeader'].stack += reward
                    break
        ouroboroslib.move_slots_to_genesis_block(slotLeaders, genesisbBlock)
        nex_genesisbBlock, next_probabilityMax = ouroboroslib.generate_genesis_block(users)
        first_15_percent = ouroboroslib.get_honest_users(genesisbBlock)
        slotLeaders = ouroboroslib.election(nex_genesisbBlock, first_15_percent, slots_number, 1)
        ouroboroslib.destroy_genesis_block(users, genesisbBlock)
        genesisbBlock = copy.deepcopy(nex_genesisbBlock)
    ouroboroslib.move_slots_to_genesis_block(slotLeaders, genesisbBlock)
    ouroboroslib.destroy_genesis_block(users, genesisbBlock)

    for i in range(len(copy_of_users)):
        user_id = ouroboroslib.get_user_index(users, copy_of_users[i].id)
        print ('Id ', copy_of_users[i].id, ' Initial amount ', copy_of_users[i].stack, ', after 1000 epochs ', users[user_id].stack )


start_mining()



