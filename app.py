import json
from pathlib import Path

import pandas as pd
import streamlit as st

from domain import new_kb
from rdr import CATEGORICAL_OPS, NUMERIC_OPS, Attribute, KnowledgeBase, fmt

KB_PATH = Path("kb.json")

st.set_page_config(page_title="RDR - Rekomendasi Laptop", layout="wide")


def load_kb() -> KnowledgeBase:
    return KnowledgeBase.load(KB_PATH) if KB_PATH.exists() else new_kb()


def persist() -> None:
    st.session_state.kb.save(KB_PATH)


S = st.session_state
S.setdefault("kb", load_kb())
S.setdefault("case", None)
S.setdefault("inf", None)
S.setdefault("teaching", False)
S.setdefault("custom", [])
S.setdefault("flash", None)
kb: KnowledgeBase = S.kb


def clear_consultation() -> None:
    S.case = S.inf = None
    S.teaching = False
    S.custom = []
    for k in ("concl_sel", "concl_new"):
        S.pop(k, None)


def on_agree() -> None:
    kb.confirm_case(S.case, S.inf.conclusion)
    persist()
    S.flash = ("success", "Rekomendasi disetujui pakar dan dikirim ke konsumen.")
    clear_consultation()


def on_disagree() -> None:
    S.teaching = True


def on_cancel() -> None:
    S.teaching = False
    S.custom = []


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Knowledge Base")
    st.metric("Jumlah rule", len(kb.rules()))
    st.metric("Kasus tercatat", len(kb.cases))
    st.download_button("Unduh KB (JSON)", json.dumps(kb.to_dict(), indent=2, ensure_ascii=False),
                       file_name="kb.json", mime="application/json")
    up = st.file_uploader("Muat KB (JSON)", type="json")
    if up is not None and st.button("Gunakan KB yang diunggah"):
        S.kb = KnowledgeBase.from_dict(json.load(up))
        persist()
        clear_consultation()
        st.rerun()
    if st.button("Reset KB (kembali ke rule default)"):
        S.kb = new_kb()
        KB_PATH.unlink(missing_ok=True)
        clear_consultation()
        st.rerun()

st.title(f"Sistem Pakar RDR - {kb.domain}")
if S.flash:
    getattr(st, S.flash[0])(S.flash[1])
    S.flash = None

tab_consult, tab_tree, tab_hist, tab_kb = st.tabs(
    ["Konsultasi", "Pohon Rule", "Riwayat Kasus", "Kelola Pengetahuan"])

# ---------------------------------------------------------------- konsultasi
with tab_consult:
    with st.form("case_form"):
        st.subheader("Data konsumen")
        values = {}
        items = list(kb.attributes.items())
        for i in range(0, len(items), 4):
            cols = st.columns(4)
            for col, (name, a) in zip(cols, items[i:i + 4]):
                with col:
                    if a.kind == "numeric":
                        values[name] = st.number_input(a.title, float(a.min), float(a.max),
                                                       float(a.default if a.default is not None else a.min),
                                                       float(a.step))
                    else:
                        values[name] = st.selectbox(a.title, a.options)
        if st.form_submit_button("Dapatkan rekomendasi", type="primary"):
            S.case = values
            S.inf = kb.infer(values)
            S.teaching = False
            S.custom = []

    if S.inf is not None:
        inf = S.inf
        st.subheader("Rekomendasi sistem")
        st.success(inf.conclusion)
        st.caption(f"Berasal dari rule R{inf.last_true.id}: IF {inf.last_true.describe()}")
        with st.expander("Jejak penelusuran pohon"):
            for r, ok in inf.path:
                st.write(f"{'✅' if ok else '❌'} R{r.id}: IF {r.describe()} → {r.conclusion}")

        if not S.teaching:
            c1, c2, _ = st.columns([1, 1, 4])
            c1.button("✅ Setuju", on_click=on_agree)
            c2.button("❌ Tidak setuju", on_click=on_disagree)
        else:
            st.subheader("Koreksi pakar")
            cs = inf.last_true.cornerstone
            if cs:
                st.info("Kasus kunci rule yang akan dianulir: " +
                        ", ".join(f"{k}={fmt(v)}" for k, v in cs.items()))
            else:
                st.info("Rule yang dianulir adalah rule default (tidak punya kasus kunci).")

            NEW = "➕ Rekomendasi baru (ketik sendiri)"
            existing = [c for c in kb.conclusions() if c != inf.conclusion]
            sel = st.selectbox("Rekomendasi yang benar menurut pakar", existing + [NEW], key="concl_sel")
            conclusion = st.text_input("Tulis rekomendasi baru", key="concl_new") if sel == NEW else sel
            options = kb.candidate_conditions(S.case, cs)
            options += [c for c in S.custom if str(c) not in {str(o) for o in options}]
            picked = st.multiselect(
                "Kondisi rule baru (dipenuhi kasus ini, tidak dipenuhi kasus kunci; digabung AND)",
                [str(c) for c in options])

            with st.expander("Tambah kondisi kustom (mis. ambang batas numerik sendiri)"):
                k1, k2, k3 = st.columns(3)
                attr = k1.selectbox("Atribut", list(kb.attributes), key="c_attr")
                a = kb.attributes[attr]
                op = k2.selectbox("Operator", NUMERIC_OPS if a.kind == "numeric" else CATEGORICAL_OPS,
                                  key=f"c_op_{attr}")
                if a.kind == "numeric":
                    val = k3.number_input("Nilai", value=float(a.default or a.min), step=a.step,
                                          key=f"c_val_{attr}")
                else:
                    val = k3.selectbox("Nilai", a.options, key=f"c_val_{attr}")
                if st.button("Tambah kondisi"):
                    try:
                        S.custom.append(kb.make_condition(attr, op, val))
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Simpan rule baru", type="primary"):
                lookup = {str(c): c for c in options}
                try:
                    rule = kb.add_rule(S.case, conclusion, [lookup[p] for p in picked], inf)
                except ValueError as e:
                    st.error(str(e))
                else:
                    persist()
                    msg = f"Rule R{rule.id} ditambahkan: IF {rule.describe()} → {rule.conclusion}"
                    S.flash = ("success", msg)
                    clear_consultation()
                    st.rerun()
            b2.button("Batal", on_click=on_cancel)

# -------------------------------------------------------------------- pohon
with tab_tree:
    hl = {r.id for r, ok in S.inf.path if ok} if S.inf else set()
    st.caption("Garis hijau = ya (true-child / perkecualian), garis putus-putus merah = tidak "
               "(false-child / alternatif). Rule kuning dilalui konsultasi terakhir. "
               "Geser ke samping jika pohon lebar.")
    svg = kb.to_svg(hl)
    st.html(f'<div style="overflow:auto; padding:4px">{svg}</div>')
    st.download_button("Unduh gambar pohon (SVG)", svg, file_name="pohon_rdr.svg", mime="image/svg+xml")
    with st.expander("Tampilan teks"):
        st.code(kb.to_text(), language=None)
    with st.expander("Diagram alternatif (Graphviz)"):
        st.graphviz_chart(kb.to_dot(hl), width="stretch")
    with st.expander("Daftar rule"):
        st.dataframe(pd.DataFrame([{"Rule": f"R{r.id}", "IF": r.describe(), "THEN": r.conclusion,
                                    "Perkecualian": f"R{r.true_child.id}" if r.true_child else "-",
                                    "Alternatif": f"R{r.false_child.id}" if r.false_child else "-"}
                                   for r in kb.rules()]), hide_index=True, width="stretch")

# ------------------------------------------------------------------ riwayat
with tab_hist:
    bad = kb.inconsistent_cases()
    if bad:
        st.warning(f"{len(bad)} kasus lama kini mendapat kesimpulan berbeda dari yang disetujui pakar.")
    if kb.cases:
        now = {id(e): kb.infer(e["case"]).conclusion for e in kb.cases}
        st.dataframe(pd.DataFrame([{**e["case"], "disetujui pakar": e["conclusion"],
                                    "kesimpulan sistem kini": now[id(e)],
                                    "konsisten": now[id(e)] == e["conclusion"]}
                                   for e in kb.cases]), hide_index=True, width='stretch')
    else:
        st.write("Belum ada kasus.")

# ------------------------------------------------------- kelola pengetahuan
def schema_changed(msg: str) -> None:
    persist()
    S.flash = ("success", msg)
    clear_consultation()
    st.rerun()


with tab_kb:
    st.caption("Pakar dapat menambah informasi baru kapan saja. Rule lama tidak diubah (prinsip RDR): "
               "pengetahuan baru masuk lewat atribut/opsi baru dan rule perkecualian.")
    st.dataframe(pd.DataFrame([{"Atribut": n, "Label": a.title, "Tipe": a.kind,
                                "Opsi / rentang": ", ".join(a.options) if a.kind == "categorical"
                                else f"{fmt(a.min)} - {fmt(a.max)}"}
                               for n, a in kb.attributes.items()]), hide_index=True, width="stretch")

    k1, k2 = st.columns(2)
    with k1:
        st.subheader("Tambah opsi pada atribut kategorikal")
        cat_attrs = [n for n, a in kb.attributes.items() if a.kind == "categorical"]
        with st.form("opt_form", clear_on_submit=True):
            o_attr = st.selectbox("Atribut", cat_attrs)
            o_val = st.text_input("Opsi baru (mis. Huawei, atau jenis kebutuhan baru)")
            if st.form_submit_button("Tambah opsi"):
                try:
                    kb.add_option(o_attr, o_val)
                except ValueError as e:
                    st.error(str(e))
                else:
                    schema_changed(f"Opsi '{o_val.strip()}' ditambahkan ke {o_attr}.")

        st.subheader("Perbaiki teks rekomendasi")
        with st.form("rename_form", clear_on_submit=True):
            r_old = st.selectbox("Rekomendasi", kb.conclusions())
            r_new = st.text_input("Teks baru")
            if st.form_submit_button("Simpan perubahan"):
                try:
                    kb.rename_conclusion(r_old, r_new)
                except ValueError as e:
                    st.error(str(e))
                else:
                    schema_changed("Teks rekomendasi diperbarui di semua rule dan riwayat.")

    with k2:
        st.subheader("Tambah atribut baru")
        with st.form("attr_form", clear_on_submit=True):
            n_name = st.text_input("Nama atribut (huruf kecil/underscore, mis. layar_sentuh)")
            n_label = st.text_input("Label tampilan")
            n_kind = st.radio("Tipe", ["categorical", "numeric"], horizontal=True)
            n_opts = st.text_input("Jika kategorikal: opsi dipisah koma (mis. Ya, Tidak)")
            n1, n2, n3, n4 = st.columns(4)
            n_min = n1.number_input("Min", value=0.0)
            n_max = n2.number_input("Maks", value=100.0)
            n_step = n3.number_input("Step", value=1.0, min_value=0.01)
            n_def = n4.number_input("Default", value=0.0)
            if st.form_submit_button("Tambah atribut"):
                try:
                    kb.add_attribute(Attribute(n_name.strip(), n_kind, n_label.strip(),
                                               [o for o in n_opts.split(",")], n_min, n_max, n_step, n_def))
                except ValueError as e:
                    st.error(str(e))
                else:
                    schema_changed(f"Atribut '{n_name.strip()}' ditambahkan. Kasus lama dianggap "
                                   "belum memiliki nilai atribut ini.")
