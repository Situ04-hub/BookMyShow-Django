import requests
import re

session = requests.Session()

# 1. Get CSRF token from login page
response = session.get('http://127.0.0.1:8000/Users/login/')
csrf_token = session.cookies.get('csrftoken')

# 2. Login
login_data = {
    'username': 'demouser',
    'password': 'password123',
    'csrfmiddlewaretoken': csrf_token
}
response = session.post('http://127.0.0.1:8000/Users/login/', data=login_data, headers={'Referer': 'http://127.0.0.1:8000/Users/login/'})

# 3. Get the first show's seat map to get CSRF token and a seat ID
response = session.get('http://127.0.0.1:8000/movies/show/1/seats/')
csrf_token = session.cookies.get('csrftoken')

# Extract an available seat ID from the HTML using regex
match = re.search(r'data-id="(\d+)"', response.text)
if not match:
    print("Could not find an available seat.")
    exit(1)
    
seat_id = match.group(1)
print(f"Found available seat ID: {seat_id}")

# 4. Book the seat using URLSearchParams style POST
post_data = {
    'seats': [seat_id]
}
headers = {
    'X-CSRFToken': csrf_token,
    'Referer': 'http://127.0.0.1:8000/movies/show/1/seats/',
    'Content-Type': 'application/x-www-form-urlencoded'
}
response = session.post('http://127.0.0.1:8000/movies/show/1/seats/', data=post_data, headers=headers)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 200 and 'booking_id' in response.json():
    print("SUCCESS: Booking workflow is perfectly functional!")
else:
    print("FAILED: Booking workflow did not return success.")
