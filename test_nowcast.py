"""Optional manual smoke test for a running local backend.

This file is named like a pytest module, so importing it during test
collection must not make a network request. Run it directly when the backend
is already running on localhost:8000.
"""

import json


def main() -> None:
    import requests

    response = requests.get("http://localhost:8000/api/nowcast/zone/1/xai", timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    try:
        print("\nResponse Data Structure:")
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print("Error parsing JSON response")


if __name__ == "__main__":
    main()
