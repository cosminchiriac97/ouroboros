from base64 import b64encode, b64decode
import ecdsa
from ecdsa import SigningKey
from ecdsa import VerifyingKey


def generate_keys():
    pri_key = SigningKey.generate(curve=ecdsa.SECP256k1)
    pub_key = pri_key.get_verifying_key()
    return b64encode(pri_key.to_pem()).decode('utf-8'), b64encode(pub_key.to_pem()).decode('utf-8')


def sign_data(private_key, message):
    signer = SigningKey.from_pem(b64decode(private_key.encode('utf-8')))
    signature = signer.sign(message.encode('utf-8'))
    return b64encode(signature).decode('utf-8')


def verify_sign(public_key, signature, message):
    vk = VerifyingKey.from_pem(b64decode(public_key.encode('utf-8')))
    try:
        result = vk.verify(b64decode(signature.encode('utf-8')), message.encode('utf-8'))
        return result
    except:
        return False