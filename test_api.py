import requests

url = "https://medilens-ai.onrender.com/scan"

files = {
    "file": ("test.jpg", open("test.jpg", "rb"), "image/jpeg")
}

res = requests.post(url, files=files)

print(res.json())