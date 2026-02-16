"""
Database Manager Module for Meat Quality Monitoring System
Handles SQLite database operations for storing sensor readings and historical data
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for meat quality monitoring system.
    Handles sensor readings, visual predictions, and fusion decisions.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file. If None, uses config.DB_PATH
        """
        self.db_path = db_path or config.DB_PATH
        self._ensure_data_directory()
        self._initialize_database()
        logger.info(f"Database manager initialized with path: {self.db_path}")
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created data directory: {db_dir}")
    
    def _initialize_database(self):
        """Initialize database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sensor readings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    device_id TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    mq135_co2 REAL NOT NULL,  -- VOC data from MQ135 sensor
                    mq136_h2s REAL NOT NULL,
                    mq137_nh3 REAL NOT NULL,
                    quality_level TEXT NOT NULL,
                    wifi_rssi INTEGER,
                    sensor_status TEXT
                )
            ''')
            
            # Visual predictions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS visual_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    species TEXT,
                    visual_status TEXT,
                    confidence REAL
                )
            ''')
            
            # Fusion decisions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fusion_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    visual_status TEXT,
                    gas_status TEXT,
                    fusion_status TEXT
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_readings(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_device ON sensor_readings(device_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_quality ON sensor_readings(quality_level)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_visual_timestamp ON visual_predictions(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_fusion_timestamp ON fusion_decisions(timestamp)')
            
            conn.commit()
            logger.info("Database schema initialized successfully")
    
    def insert_sensor_reading(self, data: Dict) -> int:
        """
        Insert a sensor reading into the database.
        
        Args:
            data: Dictionary containing sensor data with keys:
                  - timestamp (str or datetime)
                  - device_id (str)
                  - temperature (float)
                  - humidity (float)
                  - mq135_co2 (float)  -- VOC data from MQ135 sensor
                  - mq136_h2s (float)
                  - mq137_nh3 (float)
                  - quality_level (str)
                  - wifi_rssi (int, optional)
                  - sensor_status (dict, optional)
        
        Returns:
            The ID of the inserted row
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Parse timestamp
                if isinstance(data['timestamp'], str):
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                elif isinstance(data['timestamp'], (int, float)):
                    timestamp = datetime.fromtimestamp(data['timestamp'] / 1000)
                else:
                    timestamp = datetime.now()
                
                # Serialize sensor status if present
                sensor_status = json.dumps(data.get('sensor_status', {}))
                
                cursor.execute('''
                    INSERT INTO sensor_readings 
                    (timestamp, device_id, temperature, humidity, mq135_co2, mq136_h2s, mq137_nh3, quality_level, wifi_rssi, sensor_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    data['device_id'],
                    data['temperature'],
                    data['humidity'],
                    data['mq135_co2'],
                    data['mq136_h2s'],
                    data['mq137_nh3'],
                    data['quality_level'],
                    data.get('wifi_rssi'),
                    sensor_status
                ))
                
                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f"Inserted sensor reading with ID: {row_id}")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting sensor reading: {e}")
            raise
    
    def insert_visual_prediction(self, data: Dict) -> int:
        """
        Insert a visual prediction into the database.
        
        Args:
            data: Dictionary containing visual prediction data with keys:
                  - species (str)
                  - visual_status (str)
                  - confidence (float)
        
        Returns:
            The ID of the inserted row
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO visual_predictions (species, visual_status, confidence)
                    VALUES (?, ?, ?)
                ''', (
                    data['species'],
                    data['visual_status'],
                    data['confidence']
                ))
                
                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f"Inserted visual prediction with ID: {row_id}")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting visual prediction: {e}")
            raise
    
    def insert_fusion_decision(self, data: Dict) -> int:
        """
        Insert a fusion decision into the database.
        
        Args:
            data: Dictionary containing fusion decision data with keys:
                  - visual_status (str)
                  - gas_status (str)
                  - fusion_status (str)
        
        Returns:
            The ID of the inserted row
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO fusion_decisions (visual_status, gas_status, fusion_status)
                    VALUES (?, ?, ?)
                ''', (
                    data['visual_status'],
                    data['gas_status'],
                    data['fusion_status']
                ))
                
                conn.commit()
                row_id = cursor.lastrowid
                logger.debug(f"Inserted fusion decision with ID: {row_id}")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting fusion decision: {e}")
            raise
    
    def get_latest_reading(self) -> Optional[Dict]:
        """
        Get the most recent sensor reading.
        
        Returns:
            Dictionary with the latest sensor reading or None if no data
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM sensor_readings 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ''')
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest reading: {e}")
            return None
    
    def get_recent_readings(self, limit: int = 100) -> List[Dict]:
        """
        Get recent sensor readings.
        
        Args:
            limit: Maximum number of readings to return
        
        Returns:
            List of dictionaries with sensor readings
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM sensor_readings 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting recent readings: {e}")
            return []
    
    def get_readings_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Get sensor readings within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            List of dictionaries with sensor readings
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM sensor_readings 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (start_time, end_time))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting readings in range: {e}")
            return []
    
    def get_statistics(self, hours: int = 24) -> Dict:
        """
        Get statistics for sensor readings over a time period.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            Dictionary with statistics
        """
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get basic statistics
                cursor.execute('''
                    SELECT 
                        COUNT(*) as count,
                        AVG(temperature) as avg_temp,
                        AVG(humidity) as avg_humidity,
                        AVG(mq135_co2) as avg_co2,
                        AVG(mq136_h2s) as avg_h2s,
                        AVG(mq137_nh3) as avg_nh3,
                        MIN(temperature) as min_temp,
                        MAX(temperature) as max_temp,
                        MIN(mq136_h2s) as min_h2s,
                        MAX(mq136_h2s) as max_h2s,
                        MIN(mq137_nh3) as min_nh3,
                        MAX(mq137_nh3) as max_nh3
                    FROM sensor_readings 
                    WHERE timestamp >= ?
                ''', (start_time,))
                
                row = cursor.fetchone()
                
                # Get quality distribution
                cursor.execute('''
                    SELECT quality_level, COUNT(*) as count
                    FROM sensor_readings 
                    WHERE timestamp >= ?
                    GROUP BY quality_level
                ''', (start_time,))
                
                quality_dist = {row[0]: row[1] for row in cursor.fetchall()}
                
                return {
                    'count': row[0],
                    'avg_temp': round(row[1], 2) if row[1] else None,
                    'avg_humidity': round(row[2], 2) if row[2] else None,
                    'avg_co2': round(row[3], 2) if row[3] else None,
                    'avg_h2s': round(row[4], 2) if row[4] else None,
                    'avg_nh3': round(row[5], 2) if row[5] else None,
                    'min_temp': round(row[6], 2) if row[6] else None,
                    'max_temp': round(row[7], 2) if row[7] else None,
                    'min_h2s': round(row[8], 2) if row[8] else None,
                    'max_h2s': round(row[9], 2) if row[9] else None,
                    'min_nh3': round(row[10], 2) if row[10] else None,
                    'max_nh3': round(row[11], 2) if row[11] else None,
                    'quality_distribution': quality_dist
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def cleanup_old_data(self, retention_days: int = None):
        """
        Delete old data based on retention policy.
        
        Args:
            retention_days: Number of days to keep data. If None, uses config.DB_RETENTION_DAYS
        """
        if retention_days is None:
            retention_days = config.DB_RETENTION_DAYS
        
        if retention_days <= 0:
            logger.info("Data retention is disabled (retention_days <= 0)")
            return
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete old sensor readings
                cursor.execute('''
                    DELETE FROM sensor_readings 
                    WHERE timestamp < ?
                ''', (cutoff_date,))
                
                sensor_deleted = cursor.rowcount
                
                # Delete old visual predictions
                cursor.execute('''
                    DELETE FROM visual_predictions 
                    WHERE timestamp < ?
                ''', (cutoff_date,))
                
                visual_deleted = cursor.rowcount
                
                # Delete old fusion decisions
                cursor.execute('''
                    DELETE FROM fusion_decisions 
                    WHERE timestamp < ?
                ''', (cutoff_date,))
                
                fusion_deleted = cursor.rowcount
                
                conn.commit()
                
                logger.info(f"Cleanup completed: {sensor_deleted} sensor readings, "
                          f"{visual_deleted} visual predictions, {fusion_deleted} fusion decisions deleted")
                
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    def delete_all_data(self) -> dict:
        """
        Delete all data from all tables.
        
        Returns:
            Dictionary with counts of deleted records
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete all sensor readings
                cursor.execute('DELETE FROM sensor_readings')
                sensor_deleted = cursor.rowcount
                
                # Delete all visual predictions
                cursor.execute('DELETE FROM visual_predictions')
                visual_deleted = cursor.rowcount
                
                # Delete all fusion decisions
                cursor.execute('DELETE FROM fusion_decisions')
                fusion_deleted = cursor.rowcount
                
                conn.commit()
                
                logger.info(f"All data deleted: {sensor_deleted} sensor readings, "
                          f"{visual_deleted} visual predictions, {fusion_deleted} fusion decisions")
                
                return {
                    'sensor_readings': sensor_deleted,
                    'visual_predictions': visual_deleted,
                    'fusion_decisions': fusion_deleted
                }
                
        except Exception as e:
            logger.error(f"Error deleting all data: {e}")
            return {
                'sensor_readings': 0,
                'visual_predictions': 0,
                'fusion_decisions': 0,
                'error': str(e)
            }
    
    def export_to_csv(self, output_path: str = None, hours: int = 24) -> str:
        """
        Export sensor readings to CSV file.
        
        Args:
            output_path: Path to output CSV file. If None, generates default path.
            hours: Number of hours of data to export
        
        Returns:
            Path to the exported CSV file
        """
        import csv
        
        if output_path is None:
            export_dir = config.EXPORT_DIR
            if not os.path.exists(export_dir):
                os.makedirs(export_dir, exist_ok=True)
            output_path = os.path.join(export_dir, f"meat_monitor_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        start_time = datetime.now() - timedelta(hours=hours)
        
        try:
            readings = self.get_readings_in_range(start_time, datetime.now())
            
            if not readings:
                logger.warning("No data to export")
                return output_path
            
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'id', 'timestamp', 'device_id', 'temperature', 'humidity',
                    'mq135_co2', 'mq136_h2s', 'mq137_nh3', 'quality_level',
                    'wifi_rssi'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for reading in readings:
                    row = {k: reading[k] for k in fieldnames if k in reading}
                    writer.writerow(row)
            
            logger.info(f"Exported {len(readings)} readings to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise
    
    def get_database_size(self) -> int:
        """
        Get the size of the database file in bytes.
        
        Returns:
            Size of database file in bytes
        """
        try:
            return os.path.getsize(self.db_path)
        except Exception:
            return 0
    
    def get_reading_count(self) -> int:
        """
        Get the total number of sensor readings in the database.
        
        Returns:
            Number of sensor readings
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM sensor_readings')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting reading count: {e}")
            return 0


# Singleton instance for the application
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get the singleton database manager instance.
    
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def reset_db_manager():
    """Reset the singleton database manager instance."""
    global _db_manager
    _db_manager = None
