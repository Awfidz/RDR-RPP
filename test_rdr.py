import pytest
from domain import new_kb
from rdr import Condition, KnowledgeBase


def case(budget, keb, bobot=2.0, mob="Tidak", **extra):
    c = {"budget": budget, "kebutuhan": keb, "prioritas": "Performa", "mobilitas": mob,
         "bobot_maks": bobot, "layar": 14, "ram_min": 8, "storage_min": 512, "baterai_min": 6,
         "gpu": "Bebas", "os": "Bebas", "merek": "Bebas", "kondisi": "Bebas"}
    c.update(extra)
    return c


def teach(kb, c, concl, pick):
    inf = kb.infer(c)
    cands = kb.candidate_conditions(c, inf.last_true.cornerstone)
    chosen = [x for x in cands if str(x) in pick]
    assert len(chosen) == len(pick), [str(x) for x in cands]
    return kb.add_rule(c, concl, chosen, inf)


def test_default_only():
    kb = new_kb()
    inf = kb.infer(case(10, "Gaming"))
    assert inf.last_true is kb.root and inf.conclusion.startswith("Laptop all-round")


def test_exception_chain_and_false_branch():
    kb = new_kb()
    a = case(15, "Gaming")
    r1 = teach(kb, a, "Laptop gaming RTX", {"kebutuhan == Gaming"})
    assert kb.root.true_child is r1 and kb.infer(a).conclusion == "Laptop gaming RTX"

    b = case(8, "Gaming")                       # sistem salah -> perkecualian R1
    r2 = teach(kb, b, "Gaming entry-level", {"budget < 15"})
    assert r1.true_child is r2 and kb.infer(b).conclusion == "Gaming entry-level"
    assert kb.infer(a).conclusion == "Laptop gaming RTX"   # kasus lama tetap

    c = case(10, "Kuliah/Kantor", mob="Ya")     # lewat false-child R1
    r3 = teach(kb, c, "Ultrabook ringan", {"mobilitas == Ya"})
    assert r1.false_child is r3 and kb.infer(c).conclusion == "Ultrabook ringan"
    assert kb.infer(a).conclusion == "Laptop gaming RTX"
    assert kb.inconsistent_cases() == []


def test_candidates_skip_equal_and_numeric_direction():
    kb = new_kb()
    teach(kb, case(15, "Gaming"), "Gaming RTX", {"kebutuhan == Gaming"})
    new = case(8, "Gaming")
    r1 = kb.root.true_child
    cands = {str(c) for c in kb.candidate_conditions(new, r1.cornerstone)}
    assert cands == {"budget < 15", "budget <= 8"}      # atribut sama tidak jadi kandidat


def test_validation():
    kb = new_kb()
    c = case(15, "Gaming")
    inf = kb.infer(c)
    with pytest.raises(ValueError):
        kb.add_rule(c, inf.conclusion, [Condition("kebutuhan", "==", "Gaming")], inf)  # sama
    with pytest.raises(ValueError):
        kb.add_rule(c, "X", [], inf)                                                    # tanpa kondisi
    with pytest.raises(ValueError):
        kb.add_rule(c, "X", [Condition("kebutuhan", "==", "Programming/AI")], inf)      # tak dipenuhi kasus
    teach(kb, c, "Gaming RTX", {"kebutuhan == Gaming"})
    d = case(8, "Gaming")
    inf2 = kb.infer(d)
    with pytest.raises(ValueError):   # kondisi juga dipenuhi kasus kunci
        kb.add_rule(d, "Y", [Condition("kebutuhan", "==", "Gaming")], inf2)
    with pytest.raises(ValueError):
        kb.make_condition("kebutuhan", "<", "Gaming")
    with pytest.raises(ValueError):
        kb.make_condition("budget", ">", "abc")


def test_save_load(tmp_path):
    kb = new_kb()
    teach(kb, case(15, "Gaming"), "Gaming RTX", {"kebutuhan == Gaming"})
    p = tmp_path / "kb.json"
    kb.save(p)
    kb2 = KnowledgeBase.load(p)
    assert kb2.infer(case(15, "Gaming")).conclusion == "Gaming RTX"
    assert "R1" in kb2.to_dot()


def test_expert_adds_new_attribute_and_option():
    from rdr import Attribute
    kb = new_kb()
    a = case(15, "Gaming")
    teach(kb, a, "Gaming RTX", {"kebutuhan == Gaming"})
    kb.add_option("kebutuhan", "Content Creator Live Streaming")
    assert "Content Creator Live Streaming" in kb.attributes["kebutuhan"].options
    kb.add_attribute(Attribute("layar_sentuh", "categorical", "Layar sentuh?", options=["Ya", "Tidak"]))
    b = dict(case(8, "Gaming"), layar_sentuh="Ya")   # atribut baru tidak ada di kasus kunci a
    inf = kb.infer(b)
    cands = {str(c) for c in kb.candidate_conditions(b, inf.last_true.cornerstone)}
    assert "layar_sentuh == Ya" in cands
    kb.add_rule(b, "Gaming sentuh", [kb.make_condition("layar_sentuh", "==", "Ya")], inf)
    assert kb.infer(b).conclusion == "Gaming sentuh"
    assert kb.infer(a).conclusion == "Gaming RTX"
    with pytest.raises(ValueError):
        kb.add_attribute(Attribute("Layar Sentuh", "categorical", options=["a", "b"]))
    with pytest.raises(ValueError):
        kb.add_attribute(Attribute("layar_sentuh", "categorical", options=["a", "b"]))
    with pytest.raises(ValueError):
        kb.add_option("budget", "x")
    with pytest.raises(ValueError):
        kb.add_option("kebutuhan", "Gaming")


def test_rename_conclusion():
    kb = new_kb()
    a = case(15, "Gaming")
    teach(kb, a, "Gaming RTX", {"kebutuhan == Gaming"})
    kb.rename_conclusion("Gaming RTX", "Laptop Gaming RTX 4060")
    assert kb.infer(a).conclusion == "Laptop Gaming RTX 4060"
    assert kb.inconsistent_cases() == []
    with pytest.raises(ValueError):
        kb.rename_conclusion("Laptop Gaming RTX 4060", kb.root.conclusion)


def test_kb_tidak_berbagi_atribut():
    a, b = new_kb(), new_kb()
    a.add_option("merek", "Huawei")
    assert "Huawei" not in b.attributes["merek"].options
    assert "Huawei" not in new_kb().attributes["merek"].options
