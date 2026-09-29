import requests
from backend.config.settings import get_settings

def test_supabase_url():
    settings = get_settings()
    supabase_url = settings.supabase_url
    service_role_key = settings.supabase_service_role_key
    
    # Test URL format
    if not supabase_url or not service_role_key:
        print("Supabase URL or service role key is not set.")
        return
    
    # Construct the URL for testing
    test_url = f"{supabase_url}/rest/v1/zones"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}"
    }
    
    try:
        response = requests.get(test_url, headers=headers)
        print(f"Response Status: {response.status_code}")
        print(f"Response Data: {response.json()}")
    except Exception as e:
        print(f"Error accessing Supabase URL: {e}")

if __name__ == "__main__":
    test_supabase_url()