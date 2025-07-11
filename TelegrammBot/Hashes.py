from Crypto.Cipher import AES, DES3, ChaCha20
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

def aes_encrypt(plaintext: bytes, key: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plaintext, AES.block_size))
    return cipher.iv + ct_bytes

def aes_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    iv = ciphertext[:AES.block_size]
    ct = ciphertext[AES.block_size:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ct), AES.block_size) 

def des3_encrypt(plaintext: bytes, key: bytes) -> bytes:
    cipher = DES3.new(key, DES3.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plaintext, DES3.block_size))
    return cipher.iv + ct_bytes

def des3_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    iv = ciphertext[:DES3.block_size]
    ct = ciphertext[DES3.block_size:]
    cipher = DES3.new(key, DES3.MODE_CBC, iv)
    return unpad(cipher.decrypt(ct), DES3.block_size)

def chacha20_encrypt(plaintext: bytes, key: bytes) -> bytes:
    cipher = ChaCha20.new(key=key)
    ciphertext = cipher.encrypt(plaintext)
    return cipher.nonce + ciphertext

def chacha20_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    nonce = ciphertext[:8]
    ct = ciphertext[8:]
    cipher = ChaCha20.new(key=key, nonce=nonce)
    return cipher.decrypt(ct)

if __name__ == "__main__":
    aes_key = get_random_bytes(16)  
    des3_key = DES3.adjust_key_parity(get_random_bytes(16))
    chacha_key = get_random_bytes(32)  
    plaintext = b"Hello, this is a secret message!"
    aes_enc = aes_encrypt(plaintext, aes_key)
    aes_dec = aes_decrypt(aes_enc, aes_key)
    print("AES decrypted:", aes_dec)
    des3_enc = des3_encrypt(plaintext, des3_key)
    des3_dec = des3_decrypt(des3_enc, des3_key)
    print("DES3 decrypted:", des3_dec)
    chacha_enc = chacha20_encrypt(plaintext, chacha_key)
    chacha_dec = chacha20_decrypt(chacha_enc, chacha_key)
    print("ChaCha20 decrypted:", chacha_dec)
