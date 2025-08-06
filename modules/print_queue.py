import threading
import time
import logging
from typing import Optional
from .database import TodoDatabase
from .printer_manager import PrinterManager

logger = logging.getLogger(__name__)

class PrintQueueManager:
    def __init__(self, db: TodoDatabase, printer_manager: PrinterManager, mqtt_handler=None):
        """Initialize the print queue manager"""
        self.db = db
        self.printer_manager = printer_manager
        self.mqtt_handler = mqtt_handler
        self.running = False
        self.thread = None
        self.retry_interval = 30  # seconds between retry attempts
        self.max_attempts = 10  # maximum print attempts per todo
        
    def start(self):
        """Start the background print queue processor"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_queue, daemon=True)
            self.thread.start()
            logger.info("Print queue manager started")
    
    def stop(self):
        """Stop the background print queue processor"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            logger.info("Print queue manager stopped")
    
    def _process_queue(self):
        """Background process to handle the print queue"""
        logger.info("Print queue processor started")
        
        while self.running:
            try:
                # Get pending todos
                pending_todos = self.db.get_pending_todos(limit=5)
                
                for todo in pending_todos:
                    if not self.running:
                        break
                    
                    # Skip if too many attempts
                    if todo['print_attempts'] >= self.max_attempts:
                        logger.warning(f"Todo #{todo['id']} exceeded max attempts ({self.max_attempts})")
                        continue
                    
                    # Try to print
                    logger.info(f"Attempting to print todo #{todo['id']} (attempt {todo['print_attempts'] + 1})")
                    # Get language from metadata if available
                    language = None
                    if todo.get('metadata'):
                        import json
                        try:
                            metadata = json.loads(todo['metadata'])
                            language = metadata.get('language')
                        except:
                            pass
                    
                    success, message = self.printer_manager.print_todo(
                        todo['text'], 
                        todo['priority'],
                        self.mqtt_handler,
                        language=language
                    )
                    
                    if success:
                        self.db.mark_as_printed(todo['id'])
                        logger.info(f"Successfully printed todo #{todo['id']}")
                    else:
                        self.db.mark_as_failed(todo['id'], message)
                        logger.error(f"Failed to print todo #{todo['id']}: {message}")
                    
                    # Small delay between prints
                    time.sleep(2)
                
                # Wait before next check
                time.sleep(self.retry_interval)
                
            except Exception as e:
                logger.error(f"Error in print queue processor: {str(e)}")
                time.sleep(self.retry_interval)
    
    def add_todo(self, text: str, priority: int = 3, metadata: dict = None) -> tuple[bool, str, int]:
        """Add a todo and attempt to print it immediately"""
        try:
            # Add to database
            todo_id = self.db.add_todo(text, priority, metadata)
            
            # Try to print immediately with language from metadata
            language = None
            if metadata and 'language' in metadata:
                language = metadata.get('language')
            
            success, message = self.printer_manager.print_todo(text, priority, self.mqtt_handler, language=language)
            
            if success:
                self.db.mark_as_printed(todo_id)
                return True, "ToDo printed successfully", todo_id
            else:
                self.db.mark_as_failed(todo_id, message)
                return False, f"Saved to queue for retry: {message}", todo_id
                
        except Exception as e:
            logger.error(f"Error adding todo: {str(e)}")
            return False, str(e), None
    
    def retry_failed(self) -> int:
        """Manually trigger retry of all failed todos"""
        return self.db.reset_failed_todos()
    
    def get_queue_status(self) -> dict:
        """Get current queue status"""
        stats = self.db.get_stats()
        stats['queue_running'] = self.running
        stats['retry_interval'] = self.retry_interval
        stats['max_attempts'] = self.max_attempts
        return stats