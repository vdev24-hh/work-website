from hashlib import sha256

from argon2 import PasswordHasher


def hash_session(text):
    return sha256(text.encode()).hexdigest()


password_hasher = PasswordHasher()
hash_password = password_hasher.hash
verify_password = password_hasher.verify