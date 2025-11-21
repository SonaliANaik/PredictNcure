import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

# Insert admin user
c.execute("""
INSERT INTO users (username, email, password, role) 
VALUES (?, ?, ?, ?)""", 
('admin', 'admin@example.com', 'admin123', 'admin'))

conn.commit()
conn.close()

print("Admin user created!")