import sqlite3
import os
from datetime import datetime
import logging
from typing import List, Dict, Optional, Tuple
import threading
import json

logger = logging.getLogger(__name__)

class TodoDatabase:
    def __init__(self, db_path: str = 'todos.db'):
        """Initialize the database connection"""
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_database()
    
    def init_database(self):
        """Create tables if they don't exist"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Create todos table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS todos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        priority INTEGER DEFAULT 3,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        printed_at TIMESTAMP,
                        print_status TEXT DEFAULT 'pending',
                        print_attempts INTEGER DEFAULT 0,
                        last_error TEXT,
                        metadata TEXT
                    )
                ''')
                
                # Create index for faster queries
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_print_status 
                    ON todos(print_status)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_created_at 
                    ON todos(created_at)
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS login_attempts (
                        ip_address TEXT PRIMARY KEY,
                        failed_attempts INTEGER NOT NULL DEFAULT 0,
                        last_attempt_at TEXT NOT NULL
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_hash TEXT UNIQUE NOT NULL,
                        prefix TEXT NOT NULL,
                        comment TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP,
                        use_count INTEGER NOT NULL DEFAULT 0,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        is_legacy INTEGER NOT NULL DEFAULT 0
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS print_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_id INTEGER,
                        print_type TEXT NOT NULL,
                        text TEXT NOT NULL,
                        details TEXT,
                        language TEXT,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (key_id) REFERENCES api_keys(id)
                    )
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_print_events_key_created
                    ON print_events(key_id, created_at)
                ''')
                
                conn.commit()
                conn.close()
                logger.info("Database initialized successfully")
                
            except Exception as e:
                logger.error(f"Error initializing database: {str(e)}")
                raise
    
    def get_login_attempt(self, ip_address: str) -> Optional[Tuple[int, datetime]]:
        """Get the failed login count and timestamp for an IP address"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT failed_attempts, last_attempt_at
                    FROM login_attempts
                    WHERE ip_address = ?
                ''', (ip_address,))
                row = cursor.fetchone()
                conn.close()

                if row:
                    return row[0], datetime.fromisoformat(row[1])
                return None
            except Exception as e:
                logger.error(f"Error getting login attempt: {str(e)}")
                raise

    def save_login_attempt(self, ip_address: str, count: int, timestamp: datetime):
        """Save or clear failed login attempts for an IP address"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                if count > 0:
                    cursor.execute('''
                        INSERT INTO login_attempts (ip_address, failed_attempts, last_attempt_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(ip_address) DO UPDATE SET
                            failed_attempts = excluded.failed_attempts,
                            last_attempt_at = excluded.last_attempt_at
                    ''', (ip_address, count, timestamp.isoformat()))
                else:
                    cursor.execute('''
                        DELETE FROM login_attempts WHERE ip_address = ?
                    ''', (ip_address,))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Error saving login attempt: {str(e)}")
                raise

    def add_todo(self, text: str, priority: int = 3, metadata: Dict = None) -> int:
        """Add a new todo to the database"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                metadata_json = json.dumps(metadata) if metadata else None
                
                cursor.execute('''
                    INSERT INTO todos (text, priority, metadata)
                    VALUES (?, ?, ?)
                ''', (text, priority, metadata_json))
                
                todo_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                logger.info(f"Added todo #{todo_id}: {text[:50]}...")
                return todo_id
                
            except Exception as e:
                logger.error(f"Error adding todo: {str(e)}")
                raise
    
    def get_pending_todos(self, limit: int = 10) -> List[Dict]:
        """Get todos that need to be printed"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM todos 
                    WHERE print_status IN ('pending', 'failed')
                    ORDER BY 
                        CASE WHEN print_status = 'failed' THEN 0 ELSE 1 END,
                        priority DESC,
                        created_at ASC
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                conn.close()
                
                todos = []
                for row in rows:
                    todo = dict(row)
                    if todo['metadata']:
                        todo['metadata'] = json.loads(todo['metadata'])
                    todos.append(todo)
                
                return todos
                
            except Exception as e:
                logger.error(f"Error getting pending todos: {str(e)}")
                return []
    
    def mark_as_printed(self, todo_id: int) -> bool:
        """Mark a todo as successfully printed"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE todos 
                    SET print_status = 'printed',
                        printed_at = CURRENT_TIMESTAMP,
                        last_error = NULL
                    WHERE id = ?
                ''', (todo_id,))
                
                conn.commit()
                success = cursor.rowcount > 0
                conn.close()
                
                if success:
                    logger.info(f"Marked todo #{todo_id} as printed")
                return success
                
            except Exception as e:
                logger.error(f"Error marking todo as printed: {str(e)}")
                return False
    
    def mark_as_failed(self, todo_id: int, error_message: str) -> bool:
        """Mark a todo as failed to print"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE todos 
                    SET print_status = 'failed',
                        print_attempts = print_attempts + 1,
                        last_error = ?
                    WHERE id = ?
                ''', (error_message, todo_id))
                
                conn.commit()
                success = cursor.rowcount > 0
                conn.close()
                
                if success:
                    logger.info(f"Marked todo #{todo_id} as failed: {error_message}")
                return success
                
            except Exception as e:
                logger.error(f"Error marking todo as failed: {str(e)}")
                return False
    
    def get_todo_by_id(self, todo_id: int) -> Optional[Dict]:
        """Get a specific todo by ID"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM todos WHERE id = ?', (todo_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    todo = dict(row)
                    if todo['metadata']:
                        todo['metadata'] = json.loads(todo['metadata'])
                    return todo
                return None
                
            except Exception as e:
                logger.error(f"Error getting todo by ID: {str(e)}")
                return None
    
    def clear_queue(self) -> int:
        """Clear all pending and failed todos from the queue"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Count todos to be deleted
                cursor.execute('''
                    SELECT COUNT(*) FROM todos 
                    WHERE print_status IN ('pending', 'failed')
                ''')
                count = cursor.fetchone()[0]
                
                # Delete pending and failed todos
                cursor.execute('''
                    DELETE FROM todos 
                    WHERE print_status IN ('pending', 'failed')
                ''')
                
                conn.commit()
                conn.close()
                
                logger.info(f"Cleared {count} todos from queue")
                return count
                
            except Exception as e:
                logger.error(f"Error clearing queue: {str(e)}")
                return 0
    
    def get_recent_todos(self, limit: int = 50) -> List[Dict]:
        """Get recent todos for display"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM todos 
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                conn.close()
                
                todos = []
                for row in rows:
                    todo = dict(row)
                    if todo['metadata']:
                        todo['metadata'] = json.loads(todo['metadata'])
                    todos.append(todo)
                
                return todos
                
            except Exception as e:
                logger.error(f"Error getting recent todos: {str(e)}")
                return []
    
    def get_stats(self) -> Dict:
        """Get statistics about todos"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Total count
                cursor.execute('SELECT COUNT(*) FROM todos')
                total = cursor.fetchone()[0]
                
                # Count by status
                cursor.execute('''
                    SELECT print_status, COUNT(*) 
                    FROM todos 
                    GROUP BY print_status
                ''')
                status_counts = dict(cursor.fetchall())
                
                # Today's count
                cursor.execute('''
                    SELECT COUNT(*) FROM todos 
                    WHERE DATE(created_at) = DATE('now', 'localtime')
                ''')
                today_count = cursor.fetchone()[0]
                
                conn.close()
                
                return {
                    'total': total,
                    'pending': status_counts.get('pending', 0),
                    'printed': status_counts.get('printed', 0),
                    'failed': status_counts.get('failed', 0),
                    'today': today_count
                }
                
            except Exception as e:
                logger.error(f"Error getting stats: {str(e)}")
                return {
                    'total': 0,
                    'pending': 0,
                    'printed': 0,
                    'failed': 0,
                    'today': 0
                }
    
    def cleanup_old_todos(self, days: int = 30) -> int:
        """Remove old printed todos"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM todos 
                    WHERE print_status = 'printed' 
                    AND printed_at < datetime('now', '-' || ? || ' days')
                ''', (days,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old todos")
                return deleted_count
                
            except Exception as e:
                logger.error(f"Error cleaning up old todos: {str(e)}")
                return 0
    
    def reset_failed_todos(self) -> int:
        """Reset all failed todos to pending status"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE todos 
                    SET print_status = 'pending',
                        print_attempts = 0,
                        last_error = NULL
                    WHERE print_status = 'failed'
                ''')
                
                reset_count = cursor.rowcount
                conn.commit()
                conn.close()
                
                if reset_count > 0:
                    logger.info(f"Reset {reset_count} failed todos to pending")
                return reset_count
                
            except Exception as e:
                logger.error(f"Error resetting failed todos: {str(e)}")
                return 0

    def ensure_legacy_api_key(self, key_hash: str, prefix: str, comment: str):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('UPDATE api_keys SET is_active = 0 WHERE is_legacy = 1')
                cursor.execute('''
                    INSERT INTO api_keys (key_hash, prefix, comment, is_active, is_legacy)
                    VALUES (?, ?, ?, 1, 1)
                    ON CONFLICT(key_hash) DO UPDATE SET
                        prefix = excluded.prefix,
                        comment = excluded.comment,
                        is_active = 1,
                        is_legacy = 1
                ''', (key_hash, prefix, comment))
                conn.commit()
            finally:
                conn.close()

    def create_api_key(self, key_hash: str, prefix: str, comment: str) -> int:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO api_keys (key_hash, prefix, comment)
                    VALUES (?, ?, ?)
                ''', (key_hash, prefix, comment))
                key_id = cursor.lastrowid
                conn.commit()
                return key_id
            finally:
                conn.close()

    def get_api_key_by_hash(self, key_hash: str) -> Optional[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute('''
                    SELECT id, prefix, comment, is_legacy
                    FROM api_keys
                    WHERE key_hash = ? AND is_active = 1
                ''', (key_hash,)).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def has_active_api_keys(self) -> bool:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                count = conn.execute('SELECT COUNT(*) FROM api_keys WHERE is_active = 1').fetchone()[0]
                return count > 0
            finally:
                conn.close()

    def record_api_key_usage(self, key_id: int):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute('''
                    UPDATE api_keys
                    SET use_count = use_count + 1,
                        last_used_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (key_id,))
                conn.commit()
            finally:
                conn.close()

    def revoke_api_key(self, key_id: int) -> bool:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute('''
                    UPDATE api_keys
                    SET is_active = 0
                    WHERE id = ? AND is_legacy = 0 AND is_active = 1
                ''', (key_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def get_api_keys(self) -> List[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute('''
                    SELECT k.id, k.prefix, k.comment, k.created_at, k.last_used_at,
                           k.use_count, k.is_active, k.is_legacy,
                           COUNT(e.id) AS print_count
                    FROM api_keys k
                    LEFT JOIN print_events e ON e.key_id = k.id
                    GROUP BY k.id
                    ORDER BY k.is_active DESC, k.created_at DESC
                ''').fetchall()
                keys = []
                for row in rows:
                    key = dict(row)
                    key['is_active'] = bool(key['is_active'])
                    key['is_legacy'] = bool(key['is_legacy'])
                    type_rows = conn.execute('''
                        SELECT print_type, COUNT(*) AS count
                        FROM print_events
                        WHERE key_id = ?
                        GROUP BY print_type
                    ''', (key['id'],)).fetchall()
                    key['type_counts'] = {row['print_type']: row['count'] for row in type_rows}
                    keys.append(key)
                return keys
            finally:
                conn.close()

    def add_print_event(self, key_id: Optional[int], print_type: str, text: str,
                        details: Dict, language: str, status: str):
        safe_details = {
            key: value for key, value in details.items()
            if key in {'title', 'author', 'qr_size'}
        }
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute('''
                    INSERT INTO print_events (key_id, print_type, text, details, language, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    key_id,
                    print_type,
                    text,
                    json.dumps(safe_details),
                    language,
                    status,
                ))
                conn.commit()
            finally:
                conn.close()

    def get_print_events(self, limit: int = 100, key_id: Optional[int] = None) -> List[Dict]:
        limit = min(200, max(1, int(limit)))
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                query = '''
                    SELECT e.id, e.print_type, e.text, e.details, e.language,
                           e.status, e.created_at, k.comment AS key_comment,
                           k.prefix AS key_prefix
                    FROM print_events e
                    LEFT JOIN api_keys k ON k.id = e.key_id
                '''
                parameters = []
                if key_id is not None:
                    query += ' WHERE e.key_id = ?'
                    parameters.append(key_id)
                query += ' ORDER BY e.created_at DESC, e.id DESC LIMIT ?'
                parameters.append(limit)
                events = []
                for row in conn.execute(query, parameters).fetchall():
                    event = dict(row)
                    event['details'] = json.loads(event['details']) if event['details'] else {}
                    events.append(event)
                return events
            finally:
                conn.close()
