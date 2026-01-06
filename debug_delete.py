from src.database.db_manager import db_manager
import sqlite3

def test_deletion():
    sensor = "EMG"
    session_name = "DebugDelete"
    
    print(f"--- Creating session '{session_name}' ---")
    table_name = db_manager.create_session_table(sensor, session_name)
    print(f"Created table: {table_name}")
    
    # Verify existence
    tables = db_manager.get_session_tables(sensor)
    print(f"Current tables: {tables}")
    if table_name not in tables:
        print("❌ Table creation failed verification!")
        return

    print(f"--- Deleting session '{session_name}' ---")
    # Simulate DB manager direct call first
    # Note: Logic supports full table name or session name
    # We pass the full table name as the frontend does
    success = db_manager.delete_session_table(sensor, table_name)
    print(f"Deletion result: {success}")
    
    # Verify removal
    tables_after = db_manager.get_session_tables(sensor)
    print(f"Tables after delete: {tables_after}")
    
    if table_name in tables_after:
        print("❌ Table STILL EXISTS in sqlite_master!")
    else:
        print("✅ Table successfully dropped from sqlite_master.")

if __name__ == "__main__":
    test_deletion()
