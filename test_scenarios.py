"""Skenario uji RDR: dari keluaran pendek sampai panjang.

Setiap skenario membangun KB langkah demi langkah (pakar mengoreksi kasus), lalu
memeriksa:
  1. posisi rule baru (true-child / false-child dari parent yang benar),
  2. kesimpulan, rule sumber (last_true) dan panjang jejak penelusuran untuk kasus uji,
  3. bentuk pohon (teks), dan
  4. konsistensi: semua kasus yang pernah disetujui pakar tetap mendapat kesimpulan yang sama.

Hasil yang diharapkan diturunkan manual dari aturan RDR, bukan disalin dari keluaran program.
Jalankan: python -m pytest test_scenarios.py -v
"""
import xml.etree.ElementTree as ET

import pytest

from domain import DEFAULT_CONCLUSION, new_kb
from rdr import Attribute, KnowledgeBase

DEFAULT = DEFAULT_CONCLUSION


def case(**kw):
    c = {"budget": 10, "kebutuhan": "Kuliah/Kantor", "prioritas": "Performa", "mobilitas": "Tidak",
         "bobot_maks": 2.0, "layar": 14, "ram_min": 8, "storage_min": 512, "baterai_min": 6,
         "gpu": "Bebas", "os": "Bebas", "merek": "Bebas", "kondisi": "Bebas"}
    c.update(kw)
    return c


def teach(kb, step):
    """Satu siklus: sistem salah -> pakar koreksi -> rule baru dipasang di parent yang benar."""
    c = step["case"]
    inf = kb.infer(c)
    assert inf.conclusion == step["system"], "kesimpulan sistem sebelum koreksi tidak sesuai harapan"
    conds = [kb.make_condition(*t) for t in step["conds"]]
    rule = kb.add_rule(c, step["concl"], conds, inf)
    parent = next(r for r in kb.rules() if r.id == step["parent"])
    child = parent.true_child if step["branch"] == "true" else parent.false_child
    assert child is rule, f"R{rule.id} seharusnya {step['branch']}-child dari R{step['parent']}"
    return rule


def check_probes(kb, probes):
    for kw, concl, last_id, path_len in probes:
        inf = kb.infer(case(**kw))
        assert inf.conclusion == concl, kw
        assert inf.last_true.id == last_id, kw
        assert len(inf.path) == path_len, kw


# ===================================================================== PENDEK
def test_pendek_0_rule_hanya_default():
    kb = new_kb()
    assert len(kb.rules()) == 1
    assert kb.to_text() == f"R0: IF true THEN {DEFAULT}"
    check_probes(kb, [
        ({}, DEFAULT, 0, 1),
        ({"kebutuhan": "Gaming", "budget": 50}, DEFAULT, 0, 1),
    ])


def test_pendek_1_rule_gaming():
    kb = new_kb()
    teach(kb, dict(case=case(kebutuhan="Gaming", budget=25), system=DEFAULT, concl="Gaming high-end",
                   conds=[("kebutuhan", "==", "Gaming")], parent=0, branch="true"))
    assert kb.to_text() == "\n".join([
        f"R0: IF true THEN {DEFAULT}",
        "└─ ya: R1: IF kebutuhan == Gaming THEN Gaming high-end",
    ])
    check_probes(kb, [
        ({"kebutuhan": "Gaming"}, "Gaming high-end", 1, 2),
        ({"kebutuhan": "Kuliah/Kantor"}, DEFAULT, 0, 2),
    ])


# ===================================================================== SEDANG
def build_sedang():
    kb = new_kb()
    for step in [
        dict(case=case(kebutuhan="Gaming", budget=25), system=DEFAULT, concl="Gaming high-end",
             conds=[("kebutuhan", "==", "Gaming")], parent=0, branch="true"),                      # R1
        dict(case=case(kebutuhan="Gaming", budget=12), system="Gaming high-end", concl="Gaming mid-range",
             conds=[("budget", "<", 15)], parent=1, branch="true"),                                 # R2
        dict(case=case(kebutuhan="Desain Grafis", budget=20), system=DEFAULT, concl="Laptop desain grafis",
             conds=[("kebutuhan", "==", "Desain Grafis")], parent=1, branch="false"),               # R3
        dict(case=case(mobilitas="Ya", bobot_maks=1.3), system=DEFAULT, concl="Ultrabook ringan",
             conds=[("mobilitas", "==", "Ya"), ("bobot_maks", "<=", 1.5)], parent=3, branch="false"),  # R4
        dict(case=case(mobilitas="Ya", bobot_maks=1.2, baterai_min=14), system="Ultrabook ringan",
             concl="Ultrabook baterai awet", conds=[("baterai_min", ">=", 12)], parent=4, branch="true"),  # R5
    ]:
        teach(kb, step)
    return kb


def test_sedang_bentuk_pohon():
    kb = build_sedang()
    assert len(kb.rules()) == 6
    assert kb.to_text() == "\n".join([
        f"R0: IF true THEN {DEFAULT}",
        "└─ ya: R1: IF kebutuhan == Gaming THEN Gaming high-end",
        "   ├─ ya: R2: IF budget < 15 THEN Gaming mid-range",
        "   └─ tidak: R3: IF kebutuhan == Desain Grafis THEN Laptop desain grafis",
        "      └─ tidak: R4: IF mobilitas == Ya AND bobot_maks <= 1.5 THEN Ultrabook ringan",
        "         └─ ya: R5: IF baterai_min >= 12 THEN Ultrabook baterai awet",
    ])


@pytest.mark.parametrize("kw,concl,last_id,path_len", [
    ({"kebutuhan": "Gaming", "budget": 30}, "Gaming high-end", 1, 3),
    ({"kebutuhan": "Gaming", "budget": 12}, "Gaming mid-range", 2, 3),
    ({"kebutuhan": "Gaming", "budget": 15}, "Gaming high-end", 1, 3),            # batas: 15 < 15 salah
    ({"kebutuhan": "Desain Grafis"}, "Laptop desain grafis", 3, 3),
    ({"mobilitas": "Ya", "bobot_maks": 1.5, "baterai_min": 8}, "Ultrabook ringan", 4, 5),
    ({"mobilitas": "Ya", "bobot_maks": 1.5, "baterai_min": 12}, "Ultrabook baterai awet", 5, 5),
    ({"mobilitas": "Ya", "bobot_maks": 1.6}, DEFAULT, 0, 4),                    # terlalu berat -> default
    ({"kebutuhan": "Programming"}, DEFAULT, 0, 4),
])
def test_sedang_kasus_uji(kw, concl, last_id, path_len):
    check_probes(build_sedang(), [(kw, concl, last_id, path_len)])


def test_sedang_konsisten():
    assert build_sedang().inconsistent_cases() == []


# ===================================================================== PANJANG
def build_panjang():
    kb = new_kb()
    steps = [
        # --- cabang Gaming (perkecualian bersarang 4 tingkat: R1 > R2 > R3 > R4)
        dict(case=case(kebutuhan="Gaming", budget=25), system=DEFAULT, concl="Gaming high-end",
             conds=[("kebutuhan", "==", "Gaming")], parent=0, branch="true"),                      # R1
        dict(case=case(kebutuhan="Gaming", budget=12), system="Gaming high-end", concl="Gaming mid-range",
             conds=[("budget", "<", 15)], parent=1, branch="true"),                                 # R2 (ambang kustom)
        dict(case=case(kebutuhan="Gaming", budget=6), system="Gaming mid-range", concl="Gaming entry-level",
             conds=[("budget", "<", 8)], parent=2, branch="true"),                                  # R3
        dict(case=case(kebutuhan="Gaming", budget=5, kondisi="Bekas/Refurbished"),
             system="Gaming entry-level", concl="Gaming bekas/refurbished",
             conds=[("kondisi", "==", "Bekas/Refurbished")], parent=3, branch="true"),              # R4
        # --- rantai false-child: Desain > Programming > Ultrabook > Hemat
        dict(case=case(kebutuhan="Desain Grafis", budget=20), system=DEFAULT, concl="Laptop desain grafis",
             conds=[("kebutuhan", "==", "Desain Grafis")], parent=1, branch="false"),               # R5
        dict(case=case(kebutuhan="Desain Grafis", os="macOS"), system="Laptop desain grafis",
             concl="MacBook Pro untuk desain", conds=[("os", "==", "macOS")], parent=5, branch="true"),  # R6
        dict(case=case(kebutuhan="Programming"), system=DEFAULT, concl="Laptop programming",
             conds=[("kebutuhan", "==", "Programming")], parent=5, branch="false"),                 # R7
        dict(case=case(kebutuhan="Programming", ram_min=32), system="Laptop programming",
             concl="Laptop programming RAM besar", conds=[("ram_min", ">=", 32)], parent=7, branch="true"),  # R8
        dict(case=case(mobilitas="Ya", bobot_maks=1.3), system=DEFAULT, concl="Ultrabook ringan",
             conds=[("mobilitas", "==", "Ya"), ("bobot_maks", "<=", 1.5)], parent=7, branch="false"),  # R9
        dict(case=case(mobilitas="Ya", bobot_maks=1.2, baterai_min=14), system="Ultrabook ringan",
             concl="Ultrabook baterai awet", conds=[("baterai_min", ">=", 12)], parent=9, branch="true"),  # R10
        dict(case=case(budget=5, prioritas="Harga"), system=DEFAULT, concl="Laptop budget hemat",
             conds=[("budget", "<", 7), ("prioritas", "==", "Harga")], parent=9, branch="false"),   # R11
    ]
    for s in steps:
        teach(kb, s)

    # --- pakar menambah informasi baru: atribut baru + opsi baru, lalu dipakai pada rule R12
    kb.add_attribute(Attribute("layar_sentuh", "categorical", "Layar sentuh?", options=["Ya", "Tidak"]))
    kb.add_option("merek", "Huawei")
    teach(kb, dict(case=case(budget=5, prioritas="Harga", layar_sentuh="Ya"), system="Laptop budget hemat",
                   concl="Laptop 2-in-1 hemat", conds=[("layar_sentuh", "==", "Ya")],
                   parent=11, branch="true"))                                                       # R12

    # --- pakar memperbaiki teks rekomendasi
    kb.rename_conclusion("Laptop budget hemat", "Laptop hemat (di bawah 7 juta)")
    return kb


EXPECTED_TREE_PANJANG = [
    f"R0: IF true THEN {DEFAULT}",
    "└─ ya: R1: IF kebutuhan == Gaming THEN Gaming high-end",
    "   ├─ ya: R2: IF budget < 15 THEN Gaming mid-range",
    "   │  └─ ya: R3: IF budget < 8 THEN Gaming entry-level",
    "   │     └─ ya: R4: IF kondisi == Bekas/Refurbished THEN Gaming bekas/refurbished",
    "   └─ tidak: R5: IF kebutuhan == Desain Grafis THEN Laptop desain grafis",
    "      ├─ ya: R6: IF os == macOS THEN MacBook Pro untuk desain",
    "      └─ tidak: R7: IF kebutuhan == Programming THEN Laptop programming",
    "         ├─ ya: R8: IF ram_min >= 32 THEN Laptop programming RAM besar",
    "         └─ tidak: R9: IF mobilitas == Ya AND bobot_maks <= 1.5 THEN Ultrabook ringan",
    "            ├─ ya: R10: IF baterai_min >= 12 THEN Ultrabook baterai awet",
    "            └─ tidak: R11: IF budget < 7 AND prioritas == Harga THEN Laptop hemat (di bawah 7 juta)",
    "               └─ ya: R12: IF layar_sentuh == Ya THEN Laptop 2-in-1 hemat",
]

PROBES_PANJANG = [
    # (override kasus, kesimpulan, id rule sumber, panjang jejak)
    ({"kebutuhan": "Gaming", "budget": 30}, "Gaming high-end", 1, 3),
    ({"kebutuhan": "Gaming", "budget": 14}, "Gaming mid-range", 2, 4),
    ({"kebutuhan": "Gaming", "budget": 7}, "Gaming entry-level", 3, 5),
    ({"kebutuhan": "Gaming", "budget": 7, "kondisi": "Bekas/Refurbished"}, "Gaming bekas/refurbished", 4, 5),
    ({"kebutuhan": "Gaming", "budget": 15}, "Gaming high-end", 1, 3),                      # batas 15
    ({"kebutuhan": "Gaming", "budget": 8}, "Gaming mid-range", 2, 4),                       # batas 8
    ({"kebutuhan": "Gaming", "budget": 20, "kondisi": "Bekas/Refurbished"}, "Gaming high-end", 1, 3),
    ({"kebutuhan": "Gaming", "budget": 10, "mobilitas": "Ya", "bobot_maks": 1.2},
     "Gaming mid-range", 2, 4),                                                              # tak pernah ke R9
    ({"kebutuhan": "Desain Grafis", "os": "Windows"}, "Laptop desain grafis", 5, 4),
    ({"kebutuhan": "Desain Grafis", "os": "macOS"}, "MacBook Pro untuk desain", 6, 4),
    ({"kebutuhan": "Programming", "ram_min": 16}, "Laptop programming", 7, 5),
    ({"kebutuhan": "Programming", "ram_min": 64}, "Laptop programming RAM besar", 8, 5),
    ({"kebutuhan": "Programming", "mobilitas": "Ya", "bobot_maks": 1.0}, "Laptop programming", 7, 5),
    ({"mobilitas": "Ya", "bobot_maks": 1.5, "baterai_min": 8}, "Ultrabook ringan", 9, 6),
    ({"mobilitas": "Ya", "bobot_maks": 1.5, "baterai_min": 12}, "Ultrabook baterai awet", 10, 6),
    ({"mobilitas": "Ya", "bobot_maks": 1.6}, DEFAULT, 0, 6),                                # terlalu berat
    ({"budget": 5, "prioritas": "Harga"}, "Laptop hemat (di bawah 7 juta)", 11, 7),
    ({"budget": 5, "prioritas": "Harga", "layar_sentuh": "Ya"}, "Laptop 2-in-1 hemat", 12, 7),
    ({"budget": 5, "prioritas": "Performa"}, DEFAULT, 0, 6),
    ({"kebutuhan": "Multimedia/Hiburan"}, DEFAULT, 0, 6),
]


def test_panjang_bentuk_pohon():
    kb = build_panjang()
    assert len(kb.rules()) == 13
    assert kb.to_text() == "\n".join(EXPECTED_TREE_PANJANG)


@pytest.mark.parametrize("probe", PROBES_PANJANG, ids=lambda p: f"{p[1][:22]}|R{p[2]}")
def test_panjang_kasus_uji(probe):
    check_probes(build_panjang(), [probe])


def test_panjang_konsisten_setelah_semua_koreksi():
    kb = build_panjang()
    assert kb.inconsistent_cases() == []
    assert len(kb.cases) == 12          # 12 koreksi pakar tercatat sebagai kasus
    assert "Huawei" in kb.attributes["merek"].options


def test_panjang_simpan_muat_hasilnya_sama(tmp_path):
    kb = build_panjang()
    p = tmp_path / "kb.json"
    kb.save(p)
    kb2 = KnowledgeBase.load(p)
    assert kb2.to_text() == kb.to_text()
    assert kb2.inconsistent_cases() == []
    check_probes(kb2, PROBES_PANJANG)


def test_panjang_gambar_svg_valid_dan_punya_garis():
    kb = build_panjang()
    svg = kb.to_svg({0, 1, 2})
    root = ET.fromstring(svg)                                   # XML harus valid
    ns = "{http://www.w3.org/2000/svg}"
    assert len(root.findall(f"{ns}path")) == 12                 # 13 rule -> 12 garis
    assert len(root.findall(f"{ns}rect")) == 13
    assert svg.count(">ya<") == 8 and svg.count(">tidak<") == 4  # 8 true-child, 4 false-child
    # pohon kosong (hanya default) tetap valid dan tanpa garis
    s0 = ET.fromstring(new_kb().to_svg())
    assert len(s0.findall(f"{ns}path")) == 0
