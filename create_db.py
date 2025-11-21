# create_db.py
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('users.db')
c = conn.cursor()

# Create users table
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
''')

# Insert a test user with hashed password
hashed_pw = generate_password_hash("password123")  # Replace with desired password
c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", 
          ("user1", hashed_pw))

conn.commit()
conn.close()
print("Database created and test user added.")