"""Domain: rekomendasi laptop (versi luas). Ganti file ini untuk domain lain."""
from rdr import Attribute, KnowledgeBase

ATTRIBUTES = [
    Attribute("budget", "numeric", "Budget (juta Rp)", min=3, max=80, step=0.5, default=10),
    Attribute("kebutuhan", "categorical", "Kebutuhan utama",
              options=["Kuliah/Kantor", "Gaming", "Desain Grafis", "Video Editing",
                       "Programming", "AI/Data Science", "Arsitektur/3D/CAD", "Multimedia/Hiburan"]),
    Attribute("prioritas", "categorical", "Prioritas utama",
              options=["Performa", "Harga", "Portabilitas", "Baterai awet", "Kualitas layar"]),
    Attribute("mobilitas", "categorical", "Sering dibawa bepergian?", options=["Ya", "Tidak"]),
    Attribute("bobot_maks", "numeric", "Bobot maksimal (kg)", min=0.8, max=4.0, step=0.1, default=2.0),
    Attribute("layar", "numeric", "Ukuran layar (inci)", min=11, max=18, step=0.5, default=14),
    Attribute("ram_min", "numeric", "RAM minimal (GB)", min=4, max=64, step=4, default=8),
    Attribute("storage_min", "numeric", "Penyimpanan minimal (GB)", min=128, max=2048, step=128, default=512),
    Attribute("baterai_min", "numeric", "Daya tahan baterai minimal (jam)", min=3, max=20, step=1, default=6),
    Attribute("gpu", "categorical", "Butuh GPU dedicated?", options=["Bebas", "Ya", "Tidak"]),
    Attribute("os", "categorical", "Sistem operasi", options=["Bebas", "Windows", "macOS", "Linux"]),
    Attribute("merek", "categorical", "Preferensi merek",
              options=["Bebas", "Asus", "Lenovo", "Acer", "HP", "Dell", "MSI", "Apple"]),
    Attribute("kondisi", "categorical", "Kondisi barang", options=["Bebas", "Baru", "Bekas/Refurbished"]),
]

DEFAULT_CONCLUSION = "Laptop all-round (Core i5 / Ryzen 5, RAM 16 GB, SSD 512 GB)"


def new_kb() -> KnowledgeBase:
    return KnowledgeBase(ATTRIBUTES, DEFAULT_CONCLUSION, domain="Rekomendasi Laptop")
