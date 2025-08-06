import sqlite3
import os
from datetime import datetime
import logging
from typing import List, Dict, Optional
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
                
                conn.commit()
                conn.close()
                logger.info("Database initialized successfully")
                
            except Exception as e:
                logger.error(f"Error initializing database: {str(e)}")
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