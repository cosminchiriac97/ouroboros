import base64
import json
import hashlib


class Stakeholder(object):
    def __init__(self, public_key, address):

        self.public_key = public_key
        self.address = address

    def __key(self):
        return self.public_key, self.address

    def __eq__(x, y):
        return x.__key() == y.__key()

    def __hash__(self):
        return hash(self.__key())

    def to_json(self):
        json_object = {
            'public_key': self.public_key,
            'address': self.address
        }

        return json_object


class GenesisStakeholder(object):
    def __init__(self, coins, public_key, address):
        self.public_key = public_key
        self.coins = coins
        self.address = address

    def get_hash(self):
        return hashlib.sha256(base64.b64encode(json.dumps(self.to_json(), sort_keys=True).encode('utf-8'))).hexdigest()

    def to_json(self):
        json_object = {
            'public_key': self.public_key,
            'coins': self.coins,
            'address': self.address
        }

        return json_object

    @staticmethod
    def json_to_object(json):
        return GenesisStakeholder(json['coins'], json['public_key'], json['address'])