import base64
import hashlib
import os

def encrypt_payload(data: str, password: str):
    """Encrypt payload string using password and random salt (PBKDF2 + XOR/Base64 scheme)."""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    
    data_bytes = data.encode('utf-8')
    encrypted_bytes = bytearray()
    for i, b in enumerate(data_bytes):
        encrypted_bytes.append(b ^ key[i % len(key)])
        
    encrypted_str = base64.b64encode(encrypted_bytes).decode('utf-8')
    key_hash = hashlib.sha256(key).hexdigest()[:16]
    return encrypted_str, salt, key_hash

def decrypt_payload(encrypted_str: str, password: str, salt: str):
    """Decrypt payload using password and salt."""
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    encrypted_bytes = base64.b64decode(encrypted_str)
    
    decrypted_bytes = bytearray()
    for i, b in enumerate(encrypted_bytes):
        decrypted_bytes.append(b ^ key[i % len(key)])
        
    return decrypted_bytes.decode('utf-8', errors='ignore')
