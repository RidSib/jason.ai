import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def connect_to_db():
    """Connect to the Neon PostgreSQL database and return connection object"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    print(f"Connecting to database...")
    conn = psycopg2.connect(db_url)
    print("Connection established successfully!")
    return conn

def test_select(conn, table_name):
    """Test a simple SELECT query on the specified table"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        
        # Get column names
        col_names = [desc[0] for desc in cursor.description]
        
        print(f"\n--- First 5 rows from {table_name} ---")
        print(f"Columns: {', '.join(col_names)}")
        
        if not rows:
            print(f"No data found in {table_name}")
            return
            
        for row in rows:
            print(row)
            
    except Exception as e:
        print(f"Error querying {table_name}: {str(e)}")
    finally:
        cursor.close()

def test_insert(conn, table_name, data):
    """Test inserting a row into the specified table"""
    cursor = conn.cursor()
    try:
        # Create placeholders for the INSERT statement
        placeholders = ', '.join(['%s'] * len(data))
        columns = ', '.join(data.keys())
        
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING *"
        
        cursor.execute(query, list(data.values()))
        inserted_row = cursor.fetchone()
        
        conn.commit()
        print(f"\n--- Successfully inserted into {table_name} ---")
        print(f"Inserted row: {inserted_row}")
        
        # Verify the insertion by querying the table
        verify_cursor = conn.cursor()
        conditions = " AND ".join([f"{col} = %s" for col in data.keys()])
        verify_query = f"SELECT COUNT(*) FROM {table_name} WHERE {conditions}"
        verify_cursor.execute(verify_query, list(data.values()))
        count = verify_cursor.fetchone()[0]
        
        if count > 0:
            print(f"✅ Verification successful: Found {count} matching row(s) in {table_name}")
        else:
            print(f"❌ Verification failed: No matching rows found in {table_name}")
        
        verify_cursor.close()
        
    except Exception as e:
        conn.rollback()
        print(f"Error inserting into {table_name}: {str(e)}")
    finally:
        cursor.close()

def list_tables(conn):
    """List all tables in the database"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print("\n--- Available Tables ---")
        for table in tables:
            print(table[0])
            
    except Exception as e:
        print(f"Error listing tables: {str(e)}")
    finally:
        cursor.close()

def main():
    """Main function to run database tests"""
    try:
        # Connect to the database
        conn = connect_to_db()
        
        # List all tables
        list_tables(conn)
        
        # Test SELECT on users table
        test_select(conn, "users")
        
        # Test SELECT on events table
        test_select(conn, "events")

        test_select(conn, "bookings")

        new_booking = {
            "event_id": 1,
            "person_id": 1
        }
        test_insert(conn, "bookings", new_booking)
        
        # Test INSERT into bookings table
        # Uncomment and modify this if you want to test insertion
        # new_booking = {
        #     "user_id": 1,
        #     "event_id": 1
        # }
        # test_insert(conn, "bookings", new_booking)
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()