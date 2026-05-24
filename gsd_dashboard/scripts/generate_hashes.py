"""
Generate bcrypt password hashes for streamlit-authenticator.
Run once:  python scripts/generate_hashes.py

Paste the output into .streamlit/secrets.toml under [auth_credentials].
"""
import getpass

import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()


if __name__ == "__main__":
    print("Enter passwords to hash (blank line to finish).\n")
    while True:
        username = input("Username (blank to stop): ").strip()
        if not username:
            break
        plain = getpass.getpass(f"Password for {username}: ")
        hashed = hash_password(plain)
        print(f"  {username}:")
        print(f'    password: "{hashed}"')
        print()
