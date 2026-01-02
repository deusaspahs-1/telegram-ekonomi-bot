import requests, time, json, os, threading, random

# =============== AYARLAR ===============
import os
TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN = 6270127370
API = f"https://api.telegram.org/bot{TOKEN}/"
DB_FILE = "db.json"

COOLDOWN = 5
MESAJ_SAYISI = 10

DEFAULT_SETTINGS = {"mesaj_odul": 10}

# =============== MESLEKLER ===============
MESLEKLER = [
    (0, "issiz", "🚶 İşsiz", 0),
    (100, "kasiyer", "🏪 Kasiyer", 10),
    (500, "yazilimci", "💻 Yazılımcı", 25),
    (1500, "patron", "👑 Patron", 50)
]

# =============== MARKET ===============
MARKET = {
    "bisiklet": {"ad": "🚲 Bisiklet", "fiyat": 200, "bonus": 0.05},
    "motor": {"ad": "🏍️ Motor", "fiyat": 800, "bonus": 0.10},
    "araba": {"ad": "🚗 Araba", "fiyat": 2500, "bonus": 0.20},
    "ev": {"ad": "🏠 Ev", "fiyat": 1000, "bonus": 0.10},
    "ofis": {"ad": "🏢 Ofis", "fiyat": 5000, "bonus": 0.25},
    "plaza": {"ad": "🏦 Plaza", "fiyat": 15000, "bonus": 0.50}
}

# =============== SEVGİLİLER ===============
SEVGILILER = {
    "ayse": {"ad": "💃 Ayşe", "fiyat": 1000, "bonus": 0.10},
    "elif": {"ad": "💄 Elif", "fiyat": 3000, "bonus": 0.25},
    "selin": {"ad": "👠 Selin", "fiyat": 7000, "bonus": 0.50}
}

# =============== DATABASE ===============
def load():
    if not os.path.exists(DB_FILE):
        return {
            "users": {},
            "settings": DEFAULT_SETTINGS,
            "admins": [str(SUPER_ADMIN)]
        }
    d = json.load(open(DB_FILE, "r", encoding="utf-8"))
    d.setdefault("users", {})
    d.setdefault("settings", DEFAULT_SETTINGS)
    d.setdefault("admins", [str(SUPER_ADMIN)])
    return d

db = load()

def save():
    json.dump(db, open(DB_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

def get_user(uid, name):
    uid = str(uid)
    return db["users"].setdefault(uid, {
        "name": name,
        "bakiye": 0,
        "mesaj": 0,
        "son_mesaj": 0,
        "meslek": "issiz",
        "son_maas": time.time(),
        "envanter": [],
        "sevgili": None
    })

def is_admin(uid):
    return str(uid) in db["admins"]

# =============== TELEGRAM ===============
def delete_later(chat, msg_id, delay=30):
    def _del():
        try:
            requests.post(API + "deleteMessage",
                data={"chat_id": chat, "message_id": msg_id})
        except:
            pass
    threading.Timer(delay, _del).start()

def send(chat, text):
    r = requests.post(API + "sendMessage",
        data={"chat_id": chat, "text": text}).json()
    if "result" in r:
        delete_later(chat, r["result"]["message_id"])

# =============== MESLEK & BONUS ===============
def meslek_guncelle(user, chat=None, name=""):
    eski = user["meslek"]
    for limit, key, ad, _ in reversed(MESLEKLER):
        if user["bakiye"] >= limit:
            if eski != key:
                user["meslek"] = key
                user["son_maas"] = time.time()
                if chat:
                    send(chat, f"🎉 {name} meslek atladı!\n{ad}")
            break

def bonus_oran(user):
    oran = sum(MARKET[x]["bonus"] for x in user["envanter"])
    if user["sevgili"]:
        oran += SEVGILILER[user["sevgili"]]["bonus"]
    return oran

def maas_al(user):
    saat = int((time.time() - user["son_maas"]) / 3600)
    if saat > 0:
        maas = next(m[3] for m in MESLEKLER if m[1] == user["meslek"])
        gelir = int(maas * saat * (1 + bonus_oran(user)))
        user["bakiye"] += gelir
        user["son_maas"] = time.time()
        return gelir
    return 0

# =============== BOT ===============
offset = 0
print("🤖 Tam özellikli ekonomi botu çalışıyor...")

while True:
    try:
        updates = requests.get(API + "getUpdates",
            params={"offset": offset, "timeout": 60}).json()

        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            if "message" not in u or "text" not in u["message"]:
                continue

            m = u["message"]
            chat = m["chat"]["id"]
            ctype = m["chat"]["type"]
            uid = m["from"]["id"]
            name = m["from"].get("first_name", "Kullanıcı")
            text = m["text"].lower().strip()

            user = get_user(uid, name)
            is_command = text.startswith("/")

            # 💬 mesaj ödülü
            if ctype in ["group", "supergroup"] and not is_command:
                if time.time() - user["son_mesaj"] >= COOLDOWN:
                    user["son_mesaj"] = time.time()
                    user["mesaj"] += 1
                    if user["mesaj"] % MESAJ_SAYISI == 0:
                        user["bakiye"] += db["settings"]["mesaj_odul"]
                        meslek_guncelle(user, chat, name)
                        send(chat, f"💬 {name} +10₺ kazandı")

            # ===== KOMUTLAR =====
            if text == "/profil":
                meslek_ad = next(m[2] for m in MESLEKLER if m[1] == user["meslek"])
                items = ", ".join(MARKET[x]["ad"] for x in user["envanter"]) or "Yok"
                sev = SEVGILILER[user["sevgili"]]["ad"] if user["sevgili"] else "Yok"
                send(chat,
                    f"👤 {name}\n💰 {user['bakiye']}₺\n"
                    f"💼 {meslek_ad}\n💕 Sevgili: {sev}\n"
                    f"🛒 Envanter: {items}")

            elif text == "/market":
                msg = "🛒 MARKET\n"
                for k, v in MARKET.items():
                    msg += f"{k} → {v['ad']} | {v['fiyat']}₺\n"
                send(chat, msg)

            elif text.startswith("/satinal"):
                try:
                    urun = text.split()[1]
                    if urun in user["envanter"]:
                        send(chat, "❌ Zaten aldın")
                    elif user["bakiye"] >= MARKET[urun]["fiyat"]:
                        user["bakiye"] -= MARKET[urun]["fiyat"]
                        user["envanter"].append(urun)
                        meslek_guncelle(user, chat, name)
                        send(chat, f"✅ {MARKET[urun]['ad']} alındı")
                except:
                    send(chat, "❌ /satinal bisiklet")

            elif text == "/maas":
                g = maas_al(user)
                meslek_guncelle(user, chat, name)
                send(chat, f"💼 Maaş +{g}₺" if g else "⏳ Maaş yok")

            elif text.startswith("/casino"):
                try:
                    miktar = int(text.split()[1])
                    if user["bakiye"] < miktar or miktar <= 0:
                        send(chat, "❌ Geçersiz")
                    else:
                        if random.randint(1, 100) <= 50:
                            user["bakiye"] += miktar
                            send(chat, f"🎉 Kazandın +{miktar}₺")
                        else:
                            user["bakiye"] -= miktar
                            send(chat, f"💀 Kaybettin -{miktar}₺")
                        meslek_guncelle(user, chat, name)
                except:
                    send(chat, "❌ /casino 100")

            elif text == "/lider":
                top = sorted(db["users"].values(),
                             key=lambda x: x["bakiye"],
                             reverse=True)[:10]
                msg = "🏆 LİDER\n"
                for i, u in enumerate(top, 1):
                    msg += f"{i}. {u['name']} — {u['bakiye']}₺\n"
                send(chat, msg)

            elif text == "/sevgili":
                if user["sevgili"]:
                    s = SEVGILILER[user["sevgili"]]
                    send(chat, f"💕 Sevgilin: {s['ad']}")
                else:
                    msg = "💕 SEVGİLİLER\n"
                    for k, v in SEVGILILER.items():
                        msg += f"{k} → {v['ad']} | {v['fiyat']}₺\n"
                    msg += "\n/sevgilial ayse"
                    send(chat, msg)

            elif text.startswith("/sevgilial"):
                try:
                    isim = text.split()[1]
                    if user["sevgili"]:
                        send(chat, "❌ Zaten sevgilin var")
                    elif user["bakiye"] >= SEVGILILER[isim]["fiyat"]:
                        user["bakiye"] -= SEVGILILER[isim]["fiyat"]
                        user["sevgili"] = isim
                        meslek_guncelle(user, chat, name)
                        send(chat, f"💍 {SEVGILILER[isim]['ad']} artık sevgilin!")
                except:
                    send(chat, "❌ /sevgilial ayse")

            elif text == "/admin":
                if ctype != "private":
                    send(chat, "❌ Sadece DM")
                elif not is_admin(uid):
                    send(chat, "⛔ Yetkin yok")
                else:
                    send(chat,
                        "🛠️ ADMIN\n"
                        "/bakiyekle <id> <m>\n"
                        "/bakiyesil <id> <m>\n"
                        "/adminekle <id>\n"
                        "/adminsil <id>")

            elif text.startswith("/bakiyekle") and ctype == "private" and is_admin(uid):
                _, tid, m = text.split()
                db["users"][tid]["bakiye"] += int(m)
                send(chat, "✅ Eklendi")

            elif text.startswith("/bakiyesil") and ctype == "private" and is_admin(uid):
                _, tid, m = text.split()
                db["users"][tid]["bakiye"] -= int(m)
                send(chat, "✅ Silindi")

            elif text.startswith("/adminekle") and uid == SUPER_ADMIN:
                _, aid = text.split()
                if aid not in db["admins"]:
                    db["admins"].append(aid)
                    send(chat, "✅ Admin eklendi")

            elif text.startswith("/adminsil") and uid == SUPER_ADMIN:
                _, aid = text.split()
                if aid in db["admins"] and aid != str(SUPER_ADMIN):
                    db["admins"].remove(aid)
                    send(chat, "✅ Admin silindi")

            save()

        time.sleep(1)
    except Exception as e:
        print("HATA:", e)
        time.sleep(3)
