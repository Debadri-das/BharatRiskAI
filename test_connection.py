from backend.database.connection import get_supabase_admin_client

def test_connection():
    try:
        client = get_supabase_admin_client()
        print("Successfully connected to Supabase!")
        # Test a simple query
        result = client.table("zones").select("*").limit(1).execute()
        print("Query successful. Number of records returned:", result.count)
        print("Data:", result.data)
    except Exception as e:
        print(f"Error executing query: {e}")

if __name__ == "__main__":
    test_connection()