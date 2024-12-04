#!/usr/bin/env python3
from werkzeug.security import generate_password_hash

username = input("Enter username: ")
password = input("Enter password: ")
hashed = generate_password_hash(password)

print(f"\nAdd this line to web_creds.txt:")
print(f"{username}:{hashed}")
