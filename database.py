import aiosqlite
import os

# Railway persistent volume uchun /data/ papkasi ishlatiladi
# Lokal ishlab chiqishda joriy papkada saqlanadi
DATA_DIR = os.getenv("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "antigravity.db")

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
                subject TEXT DEFAULT 'Umumiy',
                title TEXT,
                file_id TEXT,
                keys TEXT,
                timer INTEGER DEFAULT 0,
                test_type TEXT DEFAULT 'pdf',
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
        # Sub-adminlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sub_admins (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sxemani yangilash (Migration)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        except: pass
        try:
            await db.execute("ALTER TABLE tests ADD COLUMN subject TEXT DEFAULT 'Umumiy'")
        except: pass
        try:
            await db.execute("ALTER TABLE tests ADD COLUMN timer INTEGER DEFAULT 0")
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

async def add_test(title, content, keys, test_type="pdf", subject="Umumiy", timer=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO tests (title, file_id, keys, test_type, subject, timer) VALUES (?, ?, ?, ?, ?, ?)", 
                         (title, content, keys.lower(), test_type, subject, timer))
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
        u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        t_count = (await (await db.execute("SELECT COUNT(*) FROM results")).fetchone())[0]
        
        # Bugun qo'shilganlar
        today_u = (await (await db.execute("SELECT COUNT(*) FROM users WHERE DATE(registered_at) = DATE('now')")).fetchone())[0]
        
        # Haftalik faol foydalanuvchilar (unique users in last 7 days)
        weekly_active = (await (await db.execute("SELECT COUNT(DISTINCT user_id) FROM results WHERE timestamp > DATETIME('now', '-7 days')")).fetchone())[0]
        
        # Eng ko'p yechilgan testlar
        popular_tests = []
        async with db.execute("""
            SELECT t.title, COUNT(r.id) as count 
            FROM results r JOIN tests t ON r.test_id = t.id 
            GROUP BY r.test_id ORDER BY count DESC LIMIT 5
        """) as cursor:
            popular_tests = [dict(r) for r in (await cursor.fetchall())]
            
        return {
            "total_users": u_count,
            "total_results": t_count,
            "today_users": today_u,
            "weekly_active": weekly_active,
            "popular_tests": popular_tests
        }

async def get_detailed_stats_by_user():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Har bir foydalanuvchi uchun REYTING (faqat har bir testning BIRINCHI urinishi hisoblanadi)
        query = """
            WITH FirstAttempts AS (
                SELECT user_id, test_id, MIN(id) as first_id
                FROM results
                GROUP BY user_id, test_id
            )
            SELECT 
                u.user_id, u.full_name, u.username, u.phone,
                COUNT(fa.test_id) as tests_count,
                SUM(r.score) as total_correct,
                SUM(r.total) as total_questions
            FROM users u
            INNER JOIN (
                SELECT user_id, test_id, MIN(id) as first_id
                FROM results
                GROUP BY user_id, test_id
            ) fa ON u.user_id = fa.user_id
            INNER JOIN results r ON fa.first_id = r.id
            GROUP BY u.user_id
            ORDER BY tests_count DESC, total_correct DESC
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_all_results_history(limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT 
                u.full_name, u.username,
                t.title as test_title,
                r.score, r.total, r.timestamp
            FROM results r
            JOIN users u ON r.user_id = u.user_id
            JOIN tests t ON r.test_id = t.id
            ORDER BY r.timestamp DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_results_by_test_detailed(test_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Faqat har bir foydalanuvchining BIRINCHI urinishini oladi
        query = """
            SELECT 
                u.full_name, u.username, u.phone,
                r.score, r.total, r.timestamp
            FROM users u
            JOIN results r ON u.user_id = r.user_id
            WHERE r.test_id = ? AND r.id IN (
                SELECT MIN(id) FROM results WHERE test_id = ? GROUP BY user_id
            )
            ORDER BY r.score DESC, r.timestamp ASC
        """
        async with db.execute(query, (test_id, test_id)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_all_results_for_excel():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT 
                u.full_name, u.username, u.phone,
                t.title as test_title,
                r.score, r.total, r.timestamp
            FROM results r
            JOIN users u ON r.user_id = u.user_id
            JOIN tests t ON r.test_id = t.id
            ORDER BY r.timestamp DESC
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

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

async def get_results_by_test_filtered(test_id, filter_type="all"):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if filter_type == "first":
            query = """
                SELECT u.full_name, u.username, u.phone, r.score, r.total, r.timestamp
                FROM results r JOIN users u ON r.user_id = u.user_id
                WHERE r.test_id = ? AND r.id IN (SELECT MIN(id) FROM results WHERE test_id = ? GROUP BY user_id)
                ORDER BY r.score DESC, r.timestamp ASC
            """
        elif filter_type == "last":
            query = """
                SELECT u.full_name, u.username, u.phone, r.score, r.total, r.timestamp
                FROM results r JOIN users u ON r.user_id = u.user_id
                WHERE r.test_id = ? AND r.id IN (SELECT MAX(id) FROM results WHERE test_id = ? GROUP BY user_id)
                ORDER BY r.score DESC, r.timestamp DESC
            """
        else: # all
            query = """
                SELECT u.full_name, u.username, u.phone, r.score, r.total, r.timestamp
                FROM results r JOIN users u ON r.user_id = u.user_id
                WHERE r.test_id = ?
                ORDER BY r.timestamp DESC
            """
        async with db.execute(query, (test_id, test_id) if filter_type != "all" else (test_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_user_best_results(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Guruhlangan natijalar: Har bir test uchun eng yuqori ball va oxirgi sana
        query = """
            SELECT t.title, MAX(r.score) as best_score, r.total, MAX(r.timestamp) as last_date
            FROM results r
            JOIN tests t ON r.test_id = t.id
            WHERE r.user_id = ?
            GROUP BY r.test_id
            ORDER BY last_date DESC
        """
        async with db.execute(query, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def update_test_keys(test_id, new_keys):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tests SET keys = ? WHERE id = ?", (new_keys.lower(), test_id))
        await db.commit()

async def get_test_subjects():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT subject FROM tests") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_tests_by_subject(subject):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tests WHERE subject = ? ORDER BY id DESC", (subject,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# ===== SUB-ADMIN FUNKSIYALARI =====
async def add_sub_admin(user_id, full_name=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO sub_admins (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
        await db.commit()

async def remove_sub_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sub_admins WHERE user_id = ?", (user_id,))
        await db.commit()

async def is_sub_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM sub_admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def get_all_sub_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id, full_name, added_at FROM sub_admins ORDER BY added_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
