import json
import requests
import uuid
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List

app = FastAPI()

# --- EN GENİŞ İZİNLER (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Her yerden gelene kapı açık
    allow_credentials=True,
    allow_methods=["*"], # Her türlü isteğe (GET, POST, PUT) izin ver
    allow_headers=["*"],
)

# --- DOSYA İŞLEMLERİ ---
def load_json(filename, default_val):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_val
    return default_val

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- YARDIMCI: TATİLLER ---
def fetch_holidays():
    year = datetime.now().year
    holidays = []
    # 2 yıllık veri çekelim
    for y in [year, year + 1]:
        try:
            url = f"https://date.nager.at/api/v3/PublicHolidays/{y}/TR"
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                for item in res.json():
                    holidays.append({
                        "id": f"holiday-{item['date']}",
                        "date": item["date"],
                        "localName": item["localName"],
                        "name": item["name"],
                        "type": "resmi"
                    })
        except:
            pass
    return holidays

# --- API YOLLARI (HER İHTİMALE KARŞI ÇİFT İSİM) ---

@app.get("/")
def root():
    return {"status": "Motor Canavar Gibi Calisiyor"}

# 1. AYARLAR / TERCİHLER (İkisine de cevap verir)
@app.get("/api/settings")
@app.get("/api/preferences")
def get_settings():
    defaults = {"notificationsEnabled": True, "defaultNotificationDays": 1, "theme": "light"}
    return load_json("settings.json", defaults)

@app.put("/api/settings")
@app.put("/api/preferences")
def update_settings(data: Dict[str, Any] = Body(...)):
    current = load_json("settings.json", {})
    current.update(data)
    save_json("settings.json", current)
    return current

# 2. TATİL YENİLEME (İki adrese de cevap verir)
@app.post("/api/holidays/refresh")
@app.post("/api/holidays/fetch")
def refresh_holidays():
    data = fetch_holidays()
    if data:
        return {"status": "success", "count": len(data)}
    # Veri çekemese bile hata vermesin, boş dönsün
    return {"status": "error", "message": "İnternet yok ama sistem ayakta"}

# 3. TATİL LİSTESİ
@app.get("/api/holidays")
@app.get("/api/holidays/all")
def get_holidays():
    return fetch_holidays()

# 4. DASHBOARD SORULARI
@app.get("/api/holidays/tomorrow")
def check_tomorrow():
    holidays = fetch_holidays()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    found = next((h for h in holidays if h["date"] == tomorrow), None)
    return {"isTomorrow": bool(found), "holiday": found}

@app.get("/api/holidays/next")
def check_next():
    holidays = fetch_holidays()
    today = datetime.now().strftime("%Y-%m-%d")
    holidays.sort(key=lambda x: x["date"])
    found = next((h for h in holidays if h["date"] > today), None)
    days = 0
    if found:
        d1 = datetime.strptime(found["date"], "%Y-%m-%d")
        d2 = datetime.strptime(today, "%Y-%m-%d")
        days = (d1 - d2).days
    return {"holiday": found, "daysUntil": days}

# 5. ETKİNLİKLER
@app.get("/api/events")
def get_events():
    return load_json("events.json", [])

@app.post("/api/events")
def create_event(evt: Dict[str, Any]):
    events = load_json("events.json", [])
    evt["id"] = str(uuid.uuid4())
    events.append(evt)
    save_json("events.json", events)
    return evt

@app.delete("/api/events/{evt_id}")
def delete_event(evt_id: str):
    events = load_json("events.json", [])
    events = [e for e in events if e.get("id") != evt_id]
    save_json("events.json", events)
    return {"status": "deleted"}

@app.put("/api/events/{evt_id}")
def update_event(evt_id: str, evt: Dict[str, Any]):
    events = load_json("events.json", [])
    for i, e in enumerate(events):
        if e.get("id") == evt_id:
            evt["id"] = evt_id
            events[i] = evt
            save_json("events.json", events)
            return evt
    raise HTTPException(status_code=404, detail="Bulunamadı")

# 6. BİLDİRİMLER
@app.get("/api/notifications")
def get_notifs():
    notifs = []
    today = datetime.now()
    # Tatiller
    for h in fetch_holidays():
        try:
            d = datetime.strptime(h["date"], "%Y-%m-%d")
            diff = (d - today).days + 1
            if diff in [1, 3, 7]:
                notifs.append({"title": f"{h['localName']} Yaklaşıyor!", "daysUntil": diff})
        except: pass
    # Etkinlikler
    for e in load_json("events.json", []):
        try:
            d = datetime.strptime(e["date"], "%Y-%m-%d")
            diff = (d - today).days + 1
            if diff == e.get("notificationDays", 1):
                notifs.append({"title": f"Hatırlatma: {e.get('title')}", "daysUntil": diff})
        except: pass
    return {"notifications": notifs}

if __name__ == "__main__":
    import uvicorn
    # PORTU 8000 OLARAK SABİTLEYELİM, STANDART OLSUN
    # 0.0.0.0 demek "Herkese kapım açık" demektir
    uvicorn.run(app, host="0.0.0.0", port=8000)