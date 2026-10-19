# NALAR — Prediction Studio (Beta)

Aplikasi web responsif untuk iPhone dan desktop.

## Fitur versi awal

- Catat hitungan peristiwa, kebiasaan, dan seri lain berdasarkan tanggal.
- Tambahkan variabel manual berupa nama, nilai angka, satuan, dan catatan.
- Lampirkan nilai variabel ke setiap observasi.
- Prediksi 1–12 periode ke depan dengan perbandingan model.
- Model: naive, rata-rata sederhana, moving average, weighted moving average, regresi linear waktu, exponential smoothing, dan regresi variabel tunggal.
- Simpan data pada browser, ekspor/impor JSON, dan ekspor CSV.
- PWA manifest, ikon, dan service worker untuk penggunaan offline.

## Menjalankan secara lokal

Gunakan Python 3.10+; tidak perlu memasang paket tambahan.

```bash
python server.py
```

Buka `http://localhost:8080` di browser. Untuk port berbeda:

```bash
PORT=8123 python server.py
```

## Backend dan privasi data

`server.py` melayani halaman web sekaligus endpoint `POST /api/forecast`. Ketika tombol **Hitung prediksi** digunakan dan backend tersedia, browser mengirim hanya observasi seri terpilih (tanggal, hitungan, dan nilai variabel numerik terpasang) agar Python menghitung hasilnya. Catatan bebas dan seri lain tidak dikirim. Backend tidak menyimpan observasi; data utama tetap berada di localStorage browser. Ketika server tidak tersedia/offline, rumus JavaScript lokal digunakan sebagai cadangan.

Sebelum aplikasi dipublikasikan untuk penggunaan umum, tambahkan autentikasi dan HTTPS. Jangan masukkan informasi sangat sensitif ke catatan.

## Menambahkan ke Home Screen iPhone

Agar bisa dipasang sebagai web app, aplikasi harus tersedia melalui URL HTTPS. Jalankan `server.py` pada hosting/server Python yang meneruskan HTTPS ke port aplikasi, atau gunakan reverse proxy HTTPS.

Di iPhone:
1. Buka URL HTTPS menggunakan Safari.
2. Tekan **Bagikan / Share**.
3. Pilih **Tambahkan ke Layar Utama / Add to Home Screen**.
4. Aktifkan **Open as Web App** bila tersedia, lalu tekan **Add**.

## Catatan model

- Tidak ada satu rumus matematika yang selalu paling akurat untuk semua peristiwa. Versi ini membandingkan beberapa metode, lalu memilih galat MAE terendah melalui uji historis berurutan jika data cukup.
- Evaluasi uji balik memerlukan beberapa titik historis; semakin banyak observasi berkala yang konsisten, semakin berguna perbandingan model.
- Regresi variabel memerlukan sekurangnya enam pasangan nilai variabel-hitungan, serta nilai variabel untuk periode yang ingin diprediksi.
- Rentang prediksi adalah kisaran indikatif berbasis 1,28 × MAE, bukan interval kepercayaan formal.
- Versi ini belum memakai OpenAI API. Perhitungan prediksi matematis dikerjakan oleh rumus Python/JavaScript agar bisa diuji dan dijelaskan; API AI dapat ditambahkan kemudian untuk membantu interpretasi teks, bukan menggantikan model statistik.
- Ekspor JSON berkala untuk membuat cadangan. Data localStorage tidak otomatis tersinkron antarperangkat.
