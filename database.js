const Database = require('better-sqlite3');
const path = require('path');
const db = new Database(path.join(__dirname, 'antigravity.db'));

// Foydalanuvchilar jadvalini yaratish
db.prepare(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`).run();

// Testlar tarixi
db.prepare(`
  CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT, -- 'text' yoki 'image'
    question TEXT,
    answer TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
  )
`).run();

// Foydalanuvchini qo'shish yoki yangilash
function saveUser(id, username, fullName) {
  const stmt = db.prepare('INSERT OR REPLACE INTO users (id, username, full_name) VALUES (?, ?, ?)');
  stmt.run(id, username, fullName);
}

// Barcha foydalanuvchilarni olish
function getAllUsers() {
  return db.prepare('SELECT id FROM users').all();
}

// Statistika
function getStats() {
  const usersCount = db.prepare('SELECT COUNT(*) as count FROM users').get().count;
  const historyCount = db.prepare('SELECT COUNT(*) as count FROM history').get().count;
  return { usersCount, historyCount };
}

// Tarixni saqlash
function saveHistory(userId, type, question, answer) {
  const stmt = db.prepare('INSERT INTO history (user_id, type, question, answer) VALUES (?, ?, ?, ?)');
  stmt.run(userId, type, question, answer);
}

module.exports = { saveUser, getAllUsers, getStats, saveHistory };
