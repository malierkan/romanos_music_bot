import json

# Dosyaları yükleyelim
with open("playlist.json", "r", encoding="utf-8") as f:
    target_playlist = json.load(f)

with open("fetched_musics.json", "r", encoding="utf-8") as f:
    source_files = json.load(f)

# Eşleştirme algoritması
final_list = []
matched_count = 0

for item in target_playlist:
    clean_name = item["name"].lower().strip()
    # Dosya ID'sini bulalım
    found_id = ""
    for s_file in source_files:
        # Uzantısız dosya adıyla listedeki adı karşılaştır
        s_name = s_file["name"].lower().replace(".mp3", "").strip()
        
        if clean_name in s_name or s_name in clean_name:
            found_id = s_file["fileid"]
            matched_count += 1
            break
    
    # Yeni objeyi oluşturalım
    item["fileid"] = found_id
    final_list.append(item)

# Kaydetme işlemi
with open("final_playlist.json", "w", encoding="utf-8") as f:
    json.dump(final_list, f, ensure_ascii=False, indent=2)

print(f"İşlem Tamam: {len(final_list)} şarkıdan {matched_count} tanesi başarıyla eşleşti.")
