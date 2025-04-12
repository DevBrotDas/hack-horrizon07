from pymongo import MongoClient
import logging
from pymongo.errors import ConnectionFailure, PyMongoError
import time

from datetime import datetime

def setup_mongo_connection(max_retries=3, retry_delay=1):
    """
    Attempt to establish MongoDB connection with retry logic
    Initializes collections with proper indexes if connection succeeds
    """
    attempt = 0
    while attempt < max_retries:
        try:
            client = MongoClient(
                'mongodb://localhost:27017/',
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                socketTimeoutMS=2000
            )
            # Verify connection with a simple command
            client.admin.command('ping')
            db = client['fir_system']
            
            # Initialize collections with indexes
            try:
                # Audit logs collection
                audit_logs = db['audit_logs']
                audit_logs.create_index([('timestamp', 1)])
                audit_logs.create_index([('action', 1)])
                
                # System events collection
                system_events = db['system_events']
                system_events.create_index([('timestamp', 1)])
                system_events.create_index([('event_type', 1)])
                
                # Insert initial system event
                system_events.insert_one({
                    'event_type': 'system_start',
                    'timestamp': datetime.utcnow(),
                    'message': 'Database initialized',
                    'status': 'success'
                })
                
                logging.info("MongoDB connection and collections initialized successfully")
                return db
                
            except PyMongoError as e:
                logging.error(f"Collection initialization failed: {e}")
                return db
                
        except ConnectionFailure as e:
            attempt += 1
            logging.warning(f"Connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            logging.error("Max retries reached. Could not connect to MongoDB.")
            return None
            
        except PyMongoError as e:
            logging.error(f"MongoDB error: {e}")
            return None
            
    return None
