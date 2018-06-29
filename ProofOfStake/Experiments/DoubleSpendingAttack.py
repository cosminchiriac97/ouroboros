import FileModule
import json
import asyncio
from aiohttp import ClientSession

headers = {'Content-type': 'application/json'}


account1 = FileModule.get_account_by_port(5001, True)
account2 = FileModule.get_account_by_port(5002, True)
account3 = FileModule.get_account_by_port(5003, True)

trans1 = {
    'receiver_public_key': account2['public_key'],
    'amount': 15000,
    'sender_public_key': account1['public_key'],
    'sender_private_key': account1['private_key']
}

trans2 = {
    'receiver_public_key': account3['public_key'],
    'amount': 15000,
    'sender_public_key': account1['public_key'],
    'sender_private_key': account1['private_key']
}


async def post_text(url, body):
    async with ClientSession() as session:
        async with session.post(url=url, data=body, headers=headers) as response:
            await response.read()


def run_broadcast_new_transaction():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = []
    task = asyncio.ensure_future(post_text(account2['address'] + 'transactions/new', json.dumps(trans1)))
    tasks.append(task)
    task = asyncio.ensure_future(post_text(account3['address'] + 'transactions/new', json.dumps(trans2)))
    tasks.append(task)
    loop.run_until_complete(asyncio.wait(tasks, timeout=3))


run_broadcast_new_transaction()
