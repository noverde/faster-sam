    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        age INTEGER
    )

    INSERT INTO users (name, email, age) VALUES ('Dotz', 'dotz@example.com', 30)
