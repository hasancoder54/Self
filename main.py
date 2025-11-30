from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import asyncio
import time

# --- FastAPI Uygulaması ---
app = FastAPI()

# Frontend'in (statik sitenin) bu API'ye erişebilmesi için CORS ayarı önemli!
# Kendi statik sitenizin URL'sini buraya ekleyin
origins = [
    "*", # Geliştirme aşamasında her yerden izin vermek için
    # "https://SENIN-RENDER-STATIC-SITE.onrender.com" # Canlıya alınca bunu kullan
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gelen verinin yapısını tanımlıyoruz
class DeleteRequest(BaseModel):
    token: str
    target_id: str

# Discord API temel URL'si
DISCORD_API = "https://discord.com/api/v9"

@app.post("/delete_messages")
async def delete_messages(data: DeleteRequest):
    token = data.token
    target_id = data.target_id
    
    # --- Discord Self-Bot için Headers (Başlıklar) ---
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Discord-Self-Bot (learning, v0.1)" # İstenilen User-Agent
    }
    
    # 1. Hedef kullanıcı ile DM kanalını bul
    try:
        # Önce tüm özel mesaj kanallarını alır
        response = requests.get(f"{DISCORD_API}/users/@me/channels", headers=headers)
        response.raise_for_status()
        dms = response.json()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=401, detail=f"Token Geçersiz veya API Hatası: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DM Kanalı Bulunurken Hata: {e}")

    dm_channel_id = None
    for dm in dms:
        if dm.get('type') == 1 and len(dm.get('recipients', [])) == 1 and dm['recipients'][0]['id'] == target_id:
            dm_channel_id = dm['id']
            break

    if not dm_channel_id:
        raise HTTPException(status_code=404, detail="Hedef Kullanıcı ile aktif DM kanalı bulunamadı.")
        
    deleted_count = 0
    message_limit = 50 # Her seferinde alınacak maksimum mesaj sayısı
    
    # 2. Mesajları döngüyle silme işlemi
    print(f"DM Kanalı ID: {dm_channel_id} ile silme işlemi başlıyor...")
    
    # Sonsuz döngü: Mesajlar bitene kadar devam eder
    while True:
        try:
            # Mesajları al
            messages_url = f"{DISCORD_API}/channels/{dm_channel_id}/messages?limit={message_limit}"
            messages_response = requests.get(messages_url, headers=headers)
            messages_response.raise_for_status()
            messages = messages_response.json()
            
            if not messages:
                print("Silinecek başka mesaj kalmadı.")
                break # Mesaj kalmayınca döngüden çık
                
            messages_to_delete = [msg for msg in messages if msg.get('author', {}).get('id') == target_id]
            # Dikkat: Self-bot, kendi mesajlarını veya başkasının mesajlarını silmek için kullanılır.
            # Kod, şu an sadece kendi mesajlarını (token sahibi) silmeye odaklanıyor.
            # Eğer sadece kendi mesajlarını silmek istersen: msg.get('author', {}).get('id') == self_user_id
            
            
            for message in messages:
                 # Mesajın kendi mesajın olup olmadığını kontrol et
                # Kendi mesajlarını silmek:
                if message.get('author', {}).get('id') == token_author_id_from_somewhere: # Token sahibinin ID'si (Örnek amaçlı)
                    # Mesaj silme işlemi
                    delete_url = f"{DISCORD_API}/channels/{dm_channel_id}/messages/{message['id']}"
                    delete_response = requests.delete(delete_url, headers=headers)
                    
                    if delete_response.status_code == 204: # Başarılı silme kodu
                        deleted_count += 1
                        print(f"Mesaj silindi: {message['id']}")
                    else:
                        print(f"Silme hatası: {delete_response.status_code} - {delete_response.text}")

                    # Discord Rate Limit'e takılmamak için bekleme süresi şart
                    await asyncio.sleep(0.5) # Yarım saniye bekle

            # Tüm mesajlar silindiyse döngüden çık (Bu kısım biraz karmaşık, mesajların tamamı silinene kadar döngü devam etmeli)
            if len(messages) < message_limit:
                 break


        except requests.exceptions.HTTPError as e:
            # Rate Limit (429) gelirse bekle
            if e.response.status_code == 429:
                retry_after = e.response.json().get('retry_after', 1) 
                print(f"Rate Limit! {retry_after} saniye bekleniyor...")
                await asyncio.sleep(retry_after)
                continue # Tekrar dene
            
            raise HTTPException(status_code=e.response.status_code, detail=f"Discord API Hatası: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Genel Hata: {e}")
            
    return {"message": f"{target_id} ile olan sohbette {deleted_count} adet mesaj silme denemesi tamamlandı. Discord'da kontrol edin."}
    