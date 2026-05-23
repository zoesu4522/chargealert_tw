import requests

TOKEN = "iv16M200o9LSL9RamE/0MXkM8YijpjnMEjid7ygq6Pjh6/v7OrhTF0ule9dx1/IAaVmam3j226K6dl+KpE4TOybTRP/Vfa/iwIRoBeNHRwepb0lHRTlpaZ42KoDMCh+PSqS1SIdEe5PdVyhVy3MFXgdB04t89/1O/w1cDnyilFU="
USER_ID = "U20e085d2f4a31893aa55ee5cd4204d66"

r = requests.post(
    "https://api.line.me/v2/bot/message/push",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    },
    json={
        "to": USER_ID,
        "messages": [{"type": "text", "text": "🔔 LINE Bot 推播測試成功!"}],
    },
    timeout=10,
)
print("Status:", r.status_code)
print("Body:", r.text)