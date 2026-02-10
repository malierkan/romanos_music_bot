Tamamdır, madem venv (sanal ortam) kullanıyorsun, README.md dosyasını bu profesyonel yaklaşıma uygun şekilde güncelledim. Sanal ortam kullanmak, kütüphanelerin birbirine karışmasını önlediği için en sağlıklı yöntemdir.

Aşağıdaki metni kopyalayıp bir dosyaya yapıştır ve adını README.md olarak kaydet.

🎵 Romanos Lokal Müzik Sistemi (v2.0 - venv Edition)
Bu sistem, Telegram sesli sohbetlerinde lokal .mp3 dosyalarını asistan bir hesap üzerinden çalmak için tasarlanmıştır. Spotify bağımlılığını ve Telegram sunucu limitlerini tamamen ortadan kaldırır.

📁 Proje Klasör Yapısı
Plaintext
.
├── .venv/               # Python Sanal Ortam klasörü
├── main.py              # Ana bot ve müzik motoru
├── get_session.py       # Asistan girişi için kod aracı
├── final_playlist.json  # Şarkı veritabanı (ID, İsim, Sözler)
├── .env                 # API ve Session bilgilerinin olduğu dosya
└── musics/              # Tüm .mp3 dosyalarınızın klasörü
🛠️ Kurulum Adımları
1. Sanal Ortamı Aktif Edin
Terminalinizi proje klasöründe açın ve venv ortamınızı başlatın:

Windows için:

Bash
.venv\Scripts\activate
Linux/macOS için:

Bash
source .venv/bin/activate
2. Kütüphaneleri Yükleyin
Sanal ortam aktifken ((venv) yazısını terminalin başında görmelisiniz), gerekli bağımlılıkları yükleyin:

Bash
pip install pyrogram==2.0.106 tgcrypto==1.2.5 py-tgcalls==0.9.7 python-dotenv==1.0.1
3. Asistan Hesabı Bağlama
Asistan hesabınızın şifresiz giriş yapabilmesi için bir SESSION_STRING almanız gerekir:

get_session.py dosyasını çalıştırın: python get_session.py

API ID, API Hash ve telefon numaranızı girin.

Telegram'dan gelen kodu girin ve terminalde oluşan uzun karakter dizisini kopyalayın.

4. Yapılandırma (.env)
.env dosyanızı oluşturun ve bilgileri eksiksiz girin:

Kod snippet'i
API_ID=123456
API_HASH=abcdef123456...
SESSION_STRING=BQD3... (Kopyaladığınız uzun kod)
JSON_FILE=final_playlist.json
MUSIC_DIR=./musics/
5. Müzik Dosyalarını Eşleştirme
Şarkıları musics/ klasörüne kopyalayın.

Kural: Şarkı dosyasının adı, final_playlist.json içindeki "name" alanıyla birebir aynı olmalıdır.

Örnek: JSON'da "name": "Ben Kiros'um" yazıyorsa dosya musics/Ben Kiros'um.mp3 olmalıdır.

🚀 Kullanım
Sanal ortam aktifken sistemi başlatmak için:

Bash
python main.py
Komutlar:
/play <id>: Şarkıyı lokalden başlatır. (Örn: /play 1)

/stop: Müziği durdurur ve asistanı odadan çıkarır.

🛡️ Özellikler & Bakım
Log Sistemi: Her işlem zaman damgasıyla terminale basılır.

Otomatik Temizlik: Komutlar 5 saniye, şarkı bilgileri 30 saniye sonra gruptan otomatik silinir.

Hata Giderme: Eğer database is locked hatası alırsanız, .session uzantılı dosyaları silip botu yeniden başlatın.
