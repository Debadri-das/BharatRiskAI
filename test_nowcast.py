import json
import requests

# Test the API endpoint directly
response = requests.get('http://localhost:8000/api/nowcast/zone/1/xai')

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

# Parse the response to validate structure
try:
    response_data = response.json()
    print("\nResponse Data Structure:")
    print(json.dumps(response_data, indent=2))
except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")