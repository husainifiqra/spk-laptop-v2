# spk_laptop_refactored.py - Sistem Pendukung Keputusan Pemilihan Laptop (Versi Perbaikan)

import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO
import re

# ---------- 1. KONFIGURASI HALAMAN DAN TAMPILAN ----------
st.set_page_config(
    page_title="SPK Laptop Pro",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CSS Kustom untuk Tampilan Modern ---
st.markdown(
    """
<style>
    /* --- Font dan Warna Dasar --- */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #f0f2f6; /* Latar belakang abu-abu muda */
        color: #1a1a1a;
    }
    /* --- Sidebar --- */
    .css-1d391kg {
        background-color: #ffffff;
        border-right: 1px solid #e6e6e6;
    }
    /* --- Tombol Utama --- */
    .stButton>button {
        background-color: #6c5ce7; /* Warna ungu modern */
        color: white;
        padding: 0.6rem 1.5rem;
        border-radius: 10px;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 14px 0 rgba(0, 0, 0, 0.1);
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #5848c4;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px 0 rgba(0, 0, 0, 0.12);
    }
    .stButton>button:active {
        background-color: #4535a1;
        transform: translateY(0);
    }
    /* --- Judul Halaman --- */
    h1, h2, h3 {
        color: #1a1a1a;
        font-weight: 700;
    }
    h1 { color: #6c5ce7; }
    /* --- Kontainer dan Kartu --- */
    .stApp > header {
        background-color: transparent;
    }
    .main .block-container {
        padding: 2rem 3rem;
    }
    /* --- Watermark --- */
    .watermark {
        position: fixed;
        bottom: 10px;
        right: 15px;
        font-size: 0.75rem;
        color: #b0b0b0;
        z-index: 9999;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ---------- 2. INISIALISASI SESSION STATE ----------
# Mengelola status login dan halaman aktif
if "username" not in st.session_state:
    st.session_state.username = None
if "page" not in st.session_state:
    st.session_state.page = "landing"
if "edited_data" not in st.session_state:
    st.session_state.edited_data = None


# ---------- 3. HALAMAN LANDING & LOGIN ----------
def show_landing_page():
    """Menampilkan halaman perkenalan aplikasi."""
    st.title("🚀 Selamat Datang di SPK Laptop Pro")
    st.image(
        "logo2.png",
        width=200,
    )
    st.markdown(
        """
    Aplikasi ini dirancang untuk membantu Anda menemukan laptop yang paling sesuai dengan kebutuhan,
    menggunakan metode SPK yang telah teruji: **Weighted Product (WP)** dan **Multi-Attribute Utility Theory (MAUT)**.

    **Fitur Unggulan:**
    - **Editor Data Interaktif:** Kelola data laptop Anda dengan mudah.
    - **Analisis Komparatif:** Bandingkan hasil dari dua metode SPK secara berdampingan.
    - **Visualisasi Dinamis:** Pahami peringkat dengan grafik yang jelas.
    - **Input Fleksibel:** Tambah data secara manual atau unggah dari file Excel.

    Silakan login untuk memulai.
    """
    )
    if st.button("Masuk ke Aplikasi", key="start_app"):
        st.session_state.page = "login"
        st.rerun()


def show_login_page():
    """Menampilkan halaman login."""
    st.title("🔐 Autentikasi Pengguna")
    st.info(
        "Masukkan nama pengguna Anda. Data dan preferensi Anda akan disimpan secara terpisah."
    )
    with st.form("login_form"):
        username = st.text_input("Nama Pengguna", placeholder="contoh: budi_pratama")
        submitted = st.form_submit_button("Login")
        if submitted:
            if username:
                st.session_state.username = username.strip().lower()
                st.session_state.page = "app"
                st.rerun()
            else:
                st.warning("Nama pengguna tidak boleh kosong.")


# --- Router Halaman Awal ---
if st.session_state.page == "landing":
    show_landing_page()
    st.stop()
if st.session_state.page == "login":
    show_login_page()
    st.stop()


# ---------- 4. PENGATURAN DATABASE DAN FUNGSI CRUD ----------
DB_PATH = "laptop_spk_v2.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()


def setup_database():
    """Membuat tabel jika belum ada."""
    c.execute(
        """
    CREATE TABLE IF NOT EXISTS laptops (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, nama TEXT,
        harga REAL, ram INTEGER, storage INTEGER, prosesor TEXT, prosesor_skor INTEGER,
        gpu TEXT, gpu_skor INTEGER, layar REAL, rating REAL
    )"""
    )
    c.execute(
        """
    CREATE TABLE IF NOT EXISTS bobot_kriteria (
        username TEXT, kriteria TEXT, bobot REAL, tipe TEXT,
        PRIMARY KEY (username, kriteria)
    )"""
    )
    conn.commit()


setup_database()

# --- Skor untuk Kriteria Kualitatif ---
prosesor_scores = {
    # Intel Core Ultra - Pola paling spesifik diutamakan
    r"core\s*ultra\s*9": 14,
    r"core\s*ultra\s*7": 12,
    r"core\s*ultra\s*5": 11,
    # Apple Silicon
    r"\bm4\b": 14,
    r"\bm3\b": 13,
    r"\bm2\b": 11,
    r"\bm1\b": 9,
    # AMD Ryzen - Mencocokkan seri spesifik
    r"ryzen\s*9\s*\d{4}": 10,
    r"ryzen\s*7\s*\d{4}": 8,
    r"ryzen\s*5\s*\d{4}": 6,
    r"ryzen\s*3\s*\d{4}": 4,
    # Intel Core i - Mencocokkan seri spesifik
    r"i9-?\d{4,5}": 10,
    r"i7-?\d{4,5}": 8,
    r"i5-?\d{4,5}": 6,
    r"i3-?\d{4,5}": 4,
    # Pola fallback yang lebih umum
    r"ryzen\s*9": 10,
    r"ryzen\s*7": 8,
    r"ryzen\s*5": 6,
    r"ryzen\s*3": 4,
    r"\bi9\b": 10,
    r"\bi7\b": 8,
    r"\bi5\b": 6,
    r"\bi3\b": 4,
    # Lainnya
    r"snapdragon": 7,
    r"mediatek": 5,
}

gpu_scores = {
    # NVIDIA GeForce RTX 40 Series
    r"rtx\s*4090": 14,
    r"rtx\s*4080": 13,
    r"rtx\s*4070": 12,
    r"rtx\s*4060": 11,
    r"rtx\s*4050": 10,
    # NVIDIA GeForce RTX 30 Series
    r"rtx\s*3080": 12,
    r"rtx\s*3070": 11,
    r"rtx\s*3060": 10,
    r"rtx\s*3050": 9,
    # NVIDIA GeForce RTX 20 Series & GTX
    r"rtx\s*2050": 8,
    r"gtx\s*1660": 7,
    r"gtx\s*1650": 7,
    # NVIDIA MX
    r"mx\s*\d{2,3}": 6,  # MX550, MX450 etc.
    # AMD Radeon RX
    r"rx\s*7\d{3}": 9,  # RX 7000 series
    r"rx\s*6\d{3}": 7,  # RX 6000 series
    # Apple Integrated
    r"apple\s*m4": 14,
    r"apple\s*m3": 12,
    r"apple\s*m2": 10,
    r"apple\s*m1": 8,
    # Intel Integrated
    r"intel\s*arc": 5.5,
    r"iris\s*xe": 4,
    r"uhd\s*graphics": 3,
    # AMD Integrated (paling umum)
    r"amd\s*radeon\s*graphics": 5,
    r"amd\s*radeon": 5,
}


# PERBAIKAN: Fungsi get_skor sekarang menggunakan regex
def get_skor(nama, skor_dict):
    nama_lower = str(nama).lower()
    # Mengurutkan berdasarkan panjang pola regex (terpanjang/paling spesifik dulu)
    for pattern, score in sorted(
        skor_dict.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if re.search(pattern, nama_lower):
            return score
    return 5  # Skor default jika tidak ada kecocokan ditemukan


# --- Fungsi-fungsi CRUD (Create, Read, Update, Delete) ---
def insert_laptop(data):
    """Menyimpan satu data laptop baru."""
    ps = get_skor(data["prosesor"], prosesor_scores)
    gs = get_skor(data["gpu"], gpu_scores)
    c.execute(
        "INSERT INTO laptops (username, nama, harga, ram, storage, prosesor, prosesor_skor, gpu, gpu_skor, layar, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            st.session_state.username,
            data["nama"],
            data["harga"],
            data["ram"],
            data["storage"],
            data["prosesor"],
            ps,
            data["gpu"],
            gs,
            data["layar"],
            data["rating"],
        ),
    )
    conn.commit()


def get_user_laptops():
    """Mengambil semua data laptop milik pengguna."""
    return pd.read_sql(
        "SELECT * FROM laptops WHERE username=?",
        conn,
        params=(st.session_state.username,),
    )


def update_laptop_data(id_to_update, data):
    """Memperbarui data laptop berdasarkan ID."""
    ps = get_skor(data["prosesor"], prosesor_scores)
    gs = get_skor(data["gpu"], gpu_scores)
    c.execute(
        "UPDATE laptops SET nama=?, harga=?, ram=?, storage=?, prosesor=?, prosesor_skor=?, gpu=?, gpu_skor=?, layar=?, rating=? WHERE id=? AND username=?",
        (
            data["nama"],
            data["harga"],
            data["ram"],
            data["storage"],
            data["prosesor"],
            ps,
            data["gpu"],
            gs,
            data["layar"],
            data["rating"],
            id_to_update,
            st.session_state.username,
        ),
    )
    conn.commit()


def delete_laptops(ids_to_delete):
    """Menghapus beberapa laptop berdasarkan daftar ID."""
    c.executemany(
        "DELETE FROM laptops WHERE id=? AND username=?",
        [(id, st.session_state.username) for id in ids_to_delete],
    )
    conn.commit()


def delete_all_user_data():
    """Menghapus semua data laptop milik pengguna."""
    c.execute("DELETE FROM laptops WHERE username=?", (st.session_state.username,))
    conn.commit()


# --- Fungsi untuk Bobot ---
def update_bobot(bobot_dict):
    """Memperbarui atau menyimpan bobot kriteria pengguna."""
    c.execute(
        "DELETE FROM bobot_kriteria WHERE username=?", (st.session_state.username,)
    )
    for k, v in bobot_dict.items():
        tipe = "cost" if k == "harga" else "benefit"
        c.execute(
            "INSERT INTO bobot_kriteria VALUES (?, ?, ?, ?)",
            (st.session_state.username, k, v, tipe),
        )
    conn.commit()


def get_bobot():
    """Mengambil bobot kriteria pengguna. Jika tidak ada, gunakan default."""
    df = pd.read_sql(
        "SELECT * FROM bobot_kriteria WHERE username=?",
        conn,
        params=(st.session_state.username,),
    )
    default_bobot = {
        "harga": 0.25,
        "ram": 0.15,
        "storage": 0.10,
        "prosesor_skor": 0.20,
        "gpu_skor": 0.20,
        "layar": 0.05,
        "rating": 0.05,
    }
    if df.empty:
        tipe = {
            k: ("cost" if k == "harga" else "benefit") for k in default_bobot.keys()
        }
        return default_bobot, tipe
    return (
        df.set_index("kriteria")["bobot"].to_dict(),
        df.set_index("kriteria")["tipe"].to_dict(),
    )


# ---------- 5. FUNGSI-FUNGSI LOGIKA SPK & UTILITAS (REFACTORED) ----------


def to_likert_generic(value, breakpoints, is_benefit=True):
    """Fungsi generik untuk konversi ke skala Likert (1-5)."""
    # Breakpoints diurutkan dari nilai terendah ke tertinggi
    if is_benefit:  # Semakin tinggi nilai, semakin bagus skornya
        if value >= breakpoints[3]:
            return 5
        if value >= breakpoints[2]:
            return 4
        if value >= breakpoints[1]:
            return 3
        if value >= breakpoints[0]:
            return 2
        return 1
    else:  # Semakin rendah nilai, semakin bagus skornya (contoh: harga)
        if value <= breakpoints[0]:
            return 5
        if value <= breakpoints[1]:
            return 4
        if value <= breakpoints[2]:
            return 3
        if value <= breakpoints[3]:
            return 2
        return 1


# --- Konfigurasi untuk konversi Likert ---
likert_config = {
    "harga": {"breakpoints": [7e6, 12e6, 18e6, 25e6], "is_benefit": False},
    "ram": {"breakpoints": [4, 8, 16, 32], "is_benefit": True},
    "storage": {"breakpoints": [256, 512, 1024, 2048], "is_benefit": True},
    "prosesor_skor": {"breakpoints": [5, 7, 9, 12], "is_benefit": True},
    "gpu_skor": {"breakpoints": [5, 7, 9, 12], "is_benefit": True},
    "layar": {"breakpoints": [14, 15, 16, 17], "is_benefit": True},
    "rating": {"breakpoints": [2, 3, 4, 4.5], "is_benefit": True},
}


def calculate_maut(df, bobot, tipe):
    """Menghitung skor MAUT menggunakan normalisasi Min-Max."""
    df_maut = df.copy()
    for k in bobot.keys():
        n_k_col, x = f"n_{k}", df_maut[k]
        min_val, max_val = x.min(), x.max()
        if min_val == max_val:
            df_maut[n_k_col] = 1.0
        else:
            if tipe.get(k) == "cost":
                df_maut[n_k_col] = (max_val - x) / (max_val - min_val)
            else:
                df_maut[n_k_col] = (x - min_val) / (max_val - min_val)

    df_maut["Skor MAUT"] = sum(df_maut[f"n_{k}"] * w for k, w in bobot.items())
    return df_maut


def calculate_wp(df, bobot, tipe):
    """Menghitung skor WP menggunakan skala Likert."""
    df_wp = df.copy()
    for k, config in likert_config.items():
        df_wp[f"likert_{k}"] = df_wp[k].apply(lambda x: to_likert_generic(x, **config))

    total_bobot = sum(bobot.values())
    bobot_norm_wp = {
        k: (w / total_bobot if tipe.get(k) == "benefit" else -w / total_bobot)
        for k, w in bobot.items()
    }

    df_wp["Skor WP"] = 1.0
    for k, w_norm in bobot_norm_wp.items():
        likert_values = df_wp[f"likert_{k}"].replace(0, 1)  # Hindari pangkat 0
        df_wp["Skor WP"] *= likert_values**w_norm
    return df_wp


# --- Utilitas Lainnya ---
def convert_df_to_excel(df):
    """Mengonversi DataFrame ke file Excel dalam format bytes."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Laptop Ranking")
    return buffer.getvalue()


def normalize_headers(df_columns):
    """Menstandarkan nama kolom dari file Excel."""
    keyword_map = {
        "nama": [r"nama.*laptop", r"produk", r"model"],
        "harga": [r"harga", r"price"],
        "ram": [r"ram", r"memori"],
        "storage": [r"storage", r"ssd", r"hdd"],
        "prosesor": [r"prosesor", r"cpu"],
        "gpu": [r"gpu", r"vga", r"graphic"],
        "layar": [r"layar", r"screen"],
        "rating": [r"rating", r"review", r"skor"],
    }
    renamed = {}
    for std_col, patterns in keyword_map.items():
        for col in df_columns:
            for pat in patterns:
                if re.search(pat, str(col).lower()):
                    renamed[col] = std_col
                    break
    return renamed


# ---------- 6. TAMPILAN UTAMA APLIKASI (SETELAH LOGIN) ----------
def show_main_app():
    """Fungsi utama yang menjalankan seluruh UI aplikasi."""

    # --- Sidebar ---
    with st.sidebar:
        st.title(f"👋 Halo, {st.session_state.username.title()}!")
        st.markdown("---")
        menu_options = {
            "📊 Hasil Rekomendasi": "bar-chart-2",
            "📋 Kelola Data Laptop": "edit",
            "➕ Tambah Data Manual": "plus-circle",
            "📂 Unggah Data dari Excel": "file-earmark-arrow-up",
            "⚖️ Atur Bobot Kriteria": "sliders",
        }
        # Menggunakan ikon dari Bootstrap
        menu_selection = st.radio(
            "Menu Navigasi:", options=menu_options.keys(), key="main_menu"
        )
        st.markdown("---")
        if st.button("🚪 Keluar (Logout)", key="logout_button"):
            st.session_state.username = None
            st.session_state.page = "landing"
            st.rerun()

    # --- Konten Halaman Utama ---
    st.header(f"Menu: {menu_selection}")

    # --- Menu: Kelola Data Laptop ---
    if menu_selection == "📋 Kelola Data Laptop":
        st.subheader("Editor Data Laptop Interaktif")
        st.info(
            "Anda dapat mengedit data langsung di tabel di bawah ini. Untuk menghapus, centang baris yang diinginkan lalu klik tombol Hapus."
        )
        df_original = get_user_laptops()
        if df_original.empty:
            st.warning(
                "Belum ada data. Silakan tambahkan melalui menu 'Tambah Data' atau 'Unggah Data'."
            )
        else:
            # Menggunakan st.data_editor
            df_editable = df_original.drop(
                columns=["username", "prosesor_skor", "gpu_skor"], errors="ignore"
            )
            df_editable.insert(0, "Hapus", False)  # Tambah kolom checkbox untuk hapus

            edited_df = st.data_editor(
                df_editable,
                key="data_editor",
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "nama": "Nama Laptop",
                    "harga": st.column_config.NumberColumn(
                        "Harga (IDR)", format="Rp %d"
                    ),
                    "ram": st.column_config.NumberColumn("RAM (GB)"),
                    "layar": st.column_config.NumberColumn(
                        "Layar (inci)", format="%.1f"
                    ),
                },
            )

            # --- Logika untuk Simpan Perubahan dan Hapus ---
            col1, col2, col3 = st.columns([2, 2, 1])
            if col1.button("💾 Simpan Perubahan", key="save_changes"):
                # Bandingkan dataframe sebelum dan sesudah diedit
                for index, row in edited_df.iterrows():
                    original_row = df_original[df_original["id"] == row["id"]]
                    if not original_row.empty and not original_row.iloc[0].equals(row):
                        update_laptop_data(row["id"], row)
                st.success("Perubahan berhasil disimpan!")
                st.rerun()

            if col2.button("❌ Hapus Baris Terpilih", key="delete_selected"):
                ids_to_delete = edited_df[edited_df["Hapus"]]["id"].tolist()
                if ids_to_delete:
                    delete_laptops(ids_to_delete)
                    st.success(f"{len(ids_to_delete)} data berhasil dihapus.")
                    st.rerun()
                else:
                    st.warning("Tidak ada baris yang dipilih untuk dihapus.")

        # --- Opsi Hapus Semua Data ---
        st.markdown("---")
        with st.expander("⚠️ Opsi Lanjutan: Hapus Semua Data"):
            st.warning(
                "PERHATIAN: Tindakan ini akan menghapus **SEMUA** data laptop Anda secara permanen dan tidak dapat dibatalkan."
            )
            if st.button("Hapus Semua Data Saya", type="primary", key="delete_all"):
                delete_all_user_data()
                st.success("Seluruh data laptop Anda telah dihapus.")
                st.rerun()

    # --- Menu: Tambah Data Manual ---
    elif menu_selection == "➕ Tambah Data Manual":
        st.subheader("Form Penambahan Data Laptop")
        with st.form("add_form", clear_on_submit=True):
            data = {
                "nama": st.text_input("Nama Laptop", help="Contoh: Macbook Air M3"),
                "harga": st.number_input("Harga (IDR)", min_value=0, step=100000),
                "ram": st.selectbox("RAM (GB)", [4, 8, 16, 32, 64]),
                "storage": st.number_input("Storage (GB)", min_value=128, step=128),
                "prosesor": st.text_input("Prosesor", help="Contoh: Apple M3"),
                "gpu": st.text_input("GPU", help="Contoh: Apple M3 10-core"),
                "layar": st.number_input(
                    "Layar (inci)",
                    min_value=10.0,
                    max_value=20.0,
                    step=0.1,
                    format="%.1f",
                ),
                "rating": st.slider("Rating (1-5)", 1.0, 5.0, 4.0, 0.1),
            }
            submitted = st.form_submit_button("Simpan Data")
            if submitted:
                if not all([data["nama"], data["prosesor"], data["gpu"]]):
                    st.error("Nama, Prosesor, dan GPU tidak boleh kosong.")
                else:
                    insert_laptop(data)
                    st.success(f"Laptop '{data['nama']}' berhasil ditambahkan!")

    # --- Menu: Unggah Data dari Excel ---
    elif menu_selection == "📂 Unggah Data dari Excel":
        st.subheader("Unggah Data Massal dari File Excel (.xlsx)")
        st.info(
            "Sistem akan mencoba mengenali kolom secara otomatis. Untuk hasil terbaik, gunakan nama kolom standar."
        )

        # --- Download Template ---
        template_df = pd.DataFrame(
            {
                "nama": ["Contoh Laptop"],
                "harga": [15000000],
                "ram": [16],
                "storage": [512],
                "prosesor": ["Contoh Prosesor i7"],
                "gpu": ["Contoh GPU RTX"],
                "layar": [15.6],
                "rating": [4.5],
            }
        )
        st.download_button(
            label="⬇️ Unduh Template Excel",
            data=convert_df_to_excel(template_df),
            file_name="template_laptop.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.markdown("---")

        file = st.file_uploader("Pilih file Excel Anda", type=["xlsx"])
        if file:
            try:
                df_excel = pd.read_excel(file)
                df_normalized = df_excel.rename(
                    columns=normalize_headers(df_excel.columns)
                )
                required_cols = list(likert_config.keys()) + [
                    "nama"
                ]  # Semua kriteria + nama
                required_cols.remove("prosesor_skor")  # Hapus kolom turunan
                required_cols.remove("gpu_skor")
                required_cols.extend(["prosesor", "gpu"])

                missing_cols = [
                    col for col in required_cols if col not in df_normalized.columns
                ]
                if missing_cols:
                    st.error(
                        f"File tidak valid. Kolom yang hilang: `{', '.join(missing_cols)}`."
                    )
                else:
                    st.success("File berhasil dibaca. Memproses...")
                    inserted_count, skipped_rows = 0, []
                    progress_bar = st.progress(0, "Memproses data...")
                    total_rows = len(df_normalized)
                    for i, row in df_normalized.iterrows():
                        try:
                            data_to_insert = row.to_dict()
                            data_to_insert["username"] = st.session_state.username
                            insert_laptop(data_to_insert)
                            inserted_count += 1
                        except Exception as e:
                            skipped_rows.append(
                                (i + 2, str(e))
                            )  # +2 untuk header dan 0-index
                        progress_bar.progress(
                            (i + 1) / total_rows,
                            f"Memproses baris {i+1}/{total_rows}...",
                        )

                    st.success(
                        f"Proses selesai! Berhasil menambahkan {inserted_count} data baru."
                    )
                    if skipped_rows:
                        st.warning(f"{len(skipped_rows)} baris dilewati karena error.")
                        st.dataframe(
                            pd.DataFrame(
                                skipped_rows,
                                columns=["Baris di Excel", "Penyebab Error"],
                            )
                        )

            except Exception as e:
                st.error(f"Gagal memproses file: {e}")

    # --- Menu: Atur Bobot Kriteria ---
    elif menu_selection == "⚖️ Atur Bobot Kriteria":
        st.subheader("Pengaturan Bobot Prioritas")
        st.info(
            "Sesuaikan bobot untuk setiap kriteria sesuai dengan preferensi Anda. Total bobot harus 100%."
        )
        current_bobot, _ = get_bobot()
        with st.form("weight_form"):
            bobot_input = {}
            cols = st.columns(2)
            for i, (k, v) in enumerate(current_bobot.items()):
                label = k.replace("_skor", "").replace("_", " ").title()
                with cols[i % 2]:
                    bobot_input[k] = st.number_input(
                        f"Bobot {label} (%)", 0, 100, int(v * 100)
                    )

            total_bobot = sum(bobot_input.values())
            st.metric(
                "Total Bobot Saat Ini",
                f"{total_bobot}%",
                "Harus 100%" if total_bobot != 100 else "Sesuai",
            )

            if st.form_submit_button("Simpan Bobot"):
                if total_bobot == 100:
                    update_bobot({k: v / 100 for k, v in bobot_input.items()})
                    st.success("Bobot berhasil diperbarui!")
                else:
                    st.error("Total bobot harus tepat 100%. Mohon periksa kembali.")

    # --- Menu: Hasil Rekomendasi ---
    elif menu_selection == "📊 Hasil Rekomendasi":
        st.subheader("Analisis dan Perankingan Laptop")
        df = get_user_laptops()
        if len(df) < 2:
            st.warning(
                "Dibutuhkan minimal 2 data laptop untuk melakukan analisis perbandingan."
            )
        else:
            bobot, tipe = get_bobot()
            df_maut = calculate_maut(df, bobot, tipe)
            df_wp = calculate_wp(df, bobot, tipe)

            # --- Gabungkan Hasil ---
            results = df[["id", "nama"]].copy()
            results = pd.merge(
                results, df_maut[["id", "Skor MAUT"]], on="id", how="left"
            )
            results = pd.merge(results, df_wp[["id", "Skor WP"]], on="id", how="left")
            results.fillna(0, inplace=True)
            results["Rank MAUT"] = (
                results["Skor MAUT"].rank(ascending=False, method="min").astype(int)
            )
            results["Rank WP"] = (
                results["Skor WP"].rank(ascending=False, method="min").astype(int)
            )

            # --- Tampilkan Hasil ---
            st.info(
                "Berikut adalah hasil perankingan laptop berdasarkan preferensi bobot Anda."
            )
            tab_summary, tab_wp, tab_maut = st.tabs(
                ["🏆 Ringkasan Peringkat", "⚙️ Detail WP", "⚙️ Detail MAUT"]
            )

            with tab_summary:
                st.dataframe(
                    results[
                        ["nama", "Skor WP", "Rank WP", "Skor MAUT", "Rank MAUT"]
                    ].sort_values("Rank WP"),
                    use_container_width=True,
                )
                st.download_button(
                    "⬇️ Unduh Hasil ke Excel",
                    convert_df_to_excel(results),
                    "ranking_laptop.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with tab_wp:
                st.subheader("Detail Perhitungan Weighted Product (WP)")
                cols_to_show = (
                    ["nama"] + [f"likert_{k}" for k in bobot.keys()] + ["Skor WP"]
                )
                st.dataframe(
                    df_wp[cols_to_show].sort_values("Skor WP", ascending=False),
                    use_container_width=True,
                )

            with tab_maut:
                st.subheader("Detail Perhitungan Multi-Attribute Utility Theory (MAUT)")
                cols_to_show = (
                    ["nama"] + [f"n_{k}" for k in bobot.keys()] + ["Skor MAUT"]
                )
                st.dataframe(
                    df_maut[cols_to_show].sort_values("Skor MAUT", ascending=False),
                    use_container_width=True,
                )

            # --- Visualisasi ---
            st.subheader("Visualisasi Peringkat")
            col1, col2 = st.columns(2)
            with col1:
                fig_wp = px.bar(
                    results.sort_values("Skor WP"),
                    x="Skor WP",
                    y="nama",
                    orientation="h",
                    title="Peringkat Metode WP",
                    text="Rank WP",
                    color_discrete_sequence=["#6c5ce7"],
                )
                st.plotly_chart(fig_wp, use_container_width=True)
            with col2:
                fig_maut = px.bar(
                    results.sort_values("Skor MAUT"),
                    x="Skor MAUT",
                    y="nama",
                    orientation="h",
                    title="Peringkat Metode MAUT",
                    text="Rank MAUT",
                    color_discrete_sequence=["#00cec9"],
                )
                st.plotly_chart(fig_maut, use_container_width=True)


# Panggil fungsi utama jika sudah login
if st.session_state.username:
    show_main_app()

# ---------- 7. WATERMARK ----------
st.markdown(
    """
    <style>
    .watermark {
        position: fixed;
        bottom: 40px; 
        left: 50%;
        transform: translateX(-50%);
        font-size: 14px;
        color: rgba(255, 255, 255, 0.5);
        text-shadow: 0 0 5px rgba(0, 0, 0, 0.5);
        z-index: 100;
        pointer-events: none;
        font-family: 'Arial', sans-serif;
    }
    </style>
    <div class="watermark">Dibuat oleh @Kelompok Batuphat © 2025</div>
    """,
    unsafe_allow_html=True,
)

