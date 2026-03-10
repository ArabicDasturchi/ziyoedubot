import aiosqlite
import os

DB_PATH = "antigravity.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Foydalanuvchilar jadvali (Phone qo'shildi)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                is_paid INTEGER DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Testlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                file_id TEXT,
                keys TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Natijalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                test_id INTEGER,
                user_answers TEXT,
                score INTEGER,
                total INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Sozlamalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Sxemani yangilash (Migration)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        except: pass
        try:
            await db.execute("ALTER TABLE tests ADD COLUMN test_type TEXT DEFAULT 'pdf'")
        except: pass
            
        # Standart sozlamalar
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('channels', '@Ziyo_ChashmasiN1,@Ziyo_kutibxonasi')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('payment_enabled', '0')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '10000')")
        await db.commit()

async def add_user(user_id, username, full_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (user_id, username, full_name))
        await db.commit()

async def update_user_phone(user_id, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def add_test(title, content, keys, test_type="pdf"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO tests (title, file_id, keys, test_type) VALUES (?, ?, ?, ?)", 
                         (title, content, keys.lower(), test_type))
        await db.commit()

async def get_all_tests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tests ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_test(test_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tests WHERE id = ?", (test_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def save_result(user_id, test_id, user_answers, score, total):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO results (user_id, test_id, user_answers, score, total) VALUES (?, ?, ?, ?, ?)", 
                         (user_id, test_id, user_answers.lower(), score, total))
        await db.commit()

async def get_user_results(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT tests.title, results.score, results.total, results.timestamp 
            FROM results 
            JOIN tests ON results.test_id = tests.id 
            WHERE results.user_id = ? 
            ORDER BY results.timestamp DESC
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def update_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        u = await db.execute("SELECT COUNT(*) FROM users")
        u_count = (await u.fetchone())[0]
        t = await db.execute("SELECT COUNT(*) FROM results")
        t_count = (await t.fetchone())[0]
        return u_count, t_count

async def delete_test(test_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tests WHERE id = ?", (test_id,))
        await db.commit()

async def delete_all_tests():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tests")
        await db.commit()

async def reset_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
