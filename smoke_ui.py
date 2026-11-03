"""Uji asap UI memakai Streamlit AppTest (jalankan: python smoke_ui.py)."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

Path("kb.json").unlink(missing_ok=True)
at = AppTest.from_file("app.py", default_timeout=30).run()
assert not at.exception, at.exception


def btn(at, text, exclude=None):
    return next(b for b in at.button if text in b.label and not (exclude and exclude in b.label))


def consult(at, kebutuhan):
    at.selectbox[0].select(kebutuhan)          # nilai form terkirim saat submit
    btn(at, "Dapatkan rekomendasi").click().run()
    assert not at.exception, at.exception
    return at.success[0].value


def teach(at, conclusion, cond):
    btn(at, "Tidak setuju").click().run()
    at.selectbox(key="concl_sel").select("➕ Rekomendasi baru (ketik sendiri)").run()
    at.text_input(key="concl_new").set_value(conclusion).run()
    at.multiselect[0].select(cond).run()
    btn(at, "Simpan rule").click().run()
    assert not at.exception, at.exception
    msg = at.success[0].value
    assert msg.startswith("Rule R"), msg
    print("  ->", msg)


print("1:", consult(at, "Gaming"))
teach(at, "Laptop gaming RTX", "kebutuhan == Gaming")
r2 = consult(at, "Gaming")
print("2:", r2)
assert r2 == "Laptop gaming RTX"
btn(at, "Setuju", exclude="Tidak").click().run()
assert not at.exception, at.exception

# pakar menambah opsi + atribut baru
at.selectbox[0].select  # form konsultasi tetap ada
assert "kebutuhan" in [a for a in at.session_state.kb.attributes]
kb = at.session_state.kb
kb.add_option("kebutuhan", "Live Streaming")
at.run()
assert "Live Streaming" in at.selectbox[0].options
print("3: opsi baru muncul di form konsultasi")
print("OK")
Path("kb.json").unlink(missing_ok=True)
