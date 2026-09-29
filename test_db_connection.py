"""
Test script to manually verify the database connection and the get_zone_nowcast function.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from backend.database.connection import get_supabase_admin_client
from backend.services.nowcast_service import get_zone_nowcast

# Test the database connection
try:
    db = get_supabase_admin_client()
    print("Database connection successful!")
    
    # Fetch zone data
    res = db.table("zones").select("*").eq("id", 1).execute()
    print(f"Zone data: {res.data}")
    
    # Test get_zone_nowcast
    zone_result = get_zone_nowcast(db, zone_id=1)
    print(f"Zone nowcast result: {zone_result}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()