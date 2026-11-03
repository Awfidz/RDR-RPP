"""Mesin Ripple Down Rule (RDR) - Single Classification RDR.

Struktur pohon biner:
  * true_child  : perkecualian (dieksekusi jika kondisi rule terpenuhi)
  * false_child : alternatif   (dieksekusi jika kondisi rule tidak terpenuhi)
Kesimpulan akhir = kesimpulan rule TERAKHIR yang terpenuhi pada penelusuran.
"""
from __future__ import annotations

import copy
import json
import operator
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

Case = dict[str, Any]

_OPS = {
    "<": operator.lt, "<=": operator.le, ">": operator.gt,
    ">=": operator.ge, "==": operator.eq, "!=": operator.ne,
}
NUMERIC_OPS = ["<", "<=", ">", ">=", "=="]
CATEGORICAL_OPS = ["==", "!="]


def fmt(v: Any) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:g}"
    return str(v)


@dataclass
class Attribute:
    name: str
    kind: str  # "numeric" | "categorical"
    label: str = ""
    options: list[str] = field(default_factory=list)
    min: float = 0.0
    max: float = 100.0
    step: float = 1.0
    default: Any = None

    @property
    def title(self) -> str:
        return self.label or self.name


@dataclass
class Condition:
    attr: str
    op: str
    value: Any

    def holds(self, case: Case) -> bool:
        v = case.get(self.attr)
        if v is None:
            return False
        try:
            return bool(_OPS[self.op](v, self.value))
        except TypeError:
            return False

    def __str__(self) -> str:
        return f"{self.attr} {self.op} {fmt(self.value)}"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Condition":
        return Condition(d["attr"], d["op"], d["value"])


@dataclass
class Rule:
    id: int
    conditions: list[Condition]
    conclusion: str
    cornerstone: Optional[Case] = None
    true_child: Optional["Rule"] = None
    false_child: Optional["Rule"] = None

    def matches(self, case: Case) -> bool:
        return all(c.holds(case) for c in self.conditions)  # [] -> selalu True

    def describe(self) -> str:
        return " AND ".join(str(c) for c in self.conditions) or "true"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conditions": [c.to_dict() for c in self.conditions],
            "conclusion": self.conclusion,
            "cornerstone": self.cornerstone,
            "true_child": self.true_child.to_dict() if self.true_child else None,
            "false_child": self.false_child.to_dict() if self.false_child else None,
        }

    @staticmethod
    def from_dict(d: dict) -> "Rule":
        return Rule(
            id=d["id"],
            conditions=[Condition.from_dict(c) for c in d["conditions"]],
            conclusion=d["conclusion"],
            cornerstone=d.get("cornerstone"),
            true_child=Rule.from_dict(d["true_child"]) if d.get("true_child") else None,
            false_child=Rule.from_dict(d["false_child"]) if d.get("false_child") else None,
        )


@dataclass
class Inference:
    conclusion: str
    last_true: Rule          # rule terakhir yang terpenuhi (sumber kesimpulan)
    last_visited: Rule       # node terakhir yang dievaluasi (tempat rule baru dipasang)
    path: list[tuple[Rule, bool]]


class KnowledgeBase:
    def __init__(self, attributes: list[Attribute], default_conclusion: str,
                 domain: str = "RDR"):
        self.domain = domain
        # salinan sendiri: opsi/atribut baru dari pakar tidak boleh bocor ke KB lain
        self.attributes: dict[str, Attribute] = {a.name: copy.deepcopy(a) for a in attributes}
        self.root = Rule(0, [], default_conclusion, None)
        self._next_id = 1
        self.cases: list[dict] = []  # riwayat kasus + kesimpulan yang disetujui pakar

    # ------------------------------------------------------------ inferensi
    def infer(self, case: Case) -> Inference:
        node: Optional[Rule] = self.root
        last_true = last_visited = None
        path: list[tuple[Rule, bool]] = []
        while node is not None:
            last_visited = node
            ok = node.matches(case)
            path.append((node, ok))
            if ok:
                last_true = node
                node = node.true_child
            else:
                node = node.false_child
        assert last_true is not None and last_visited is not None
        return Inference(last_true.conclusion, last_true, last_visited, path)

    # ---------------------------------------------------- akuisisi pengetahuan
    def make_condition(self, attr: str, op: str, value: Any) -> Condition:
        """Buat kondisi tervalidasi terhadap skema atribut."""
        if attr not in self.attributes:
            raise ValueError(f"Atribut tidak dikenal: {attr}")
        a = self.attributes[attr]
        if a.kind == "numeric":
            if op not in NUMERIC_OPS:
                raise ValueError(f"Operator {op} tidak valid untuk atribut numerik")
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError("Nilai harus berupa angka")
        else:
            if op not in CATEGORICAL_OPS:
                raise ValueError(f"Operator {op} tidak valid untuk atribut kategorikal")
            if value not in a.options:
                raise ValueError(f"Nilai '{value}' tidak ada di opsi {a.options}")
        return Condition(attr, op, value)

    def candidate_conditions(self, case: Case, cornerstone: Optional[Case]) -> list[Condition]:
        """Kondisi yang dipenuhi kasus baru dan TIDAK dipenuhi kasus kunci."""
        out: list[Condition] = []
        for name, a in self.attributes.items():
            if name not in case:
                continue
            new = case[name]
            if cornerstone is None:  # rule default: tidak ada kasus kunci
                if a.kind == "numeric":
                    out += [Condition(name, ">=", new), Condition(name, "<=", new)]
                else:
                    out.append(Condition(name, "==", new))
                continue
            old = cornerstone.get(name)
            if old is None:  # atribut baru, belum ada pada kasus kunci -> pasti membedakan
                if a.kind == "numeric":
                    out += [Condition(name, ">=", new), Condition(name, "<=", new)]
                else:
                    out.append(Condition(name, "==", new))
                continue
            if old == new:
                continue  # atribut tidak membedakan kedua kasus
            if a.kind == "numeric":
                if new > old:
                    out += [Condition(name, ">", old), Condition(name, ">=", new)]
                else:
                    out += [Condition(name, "<", old), Condition(name, "<=", new)]
            else:
                out += [Condition(name, "==", new), Condition(name, "!=", old)]
        return out

    def add_rule(self, case: Case, conclusion: str, conditions: list[Condition],
                 inference: Inference) -> Rule:
        conclusion = conclusion.strip()
        if not conclusion:
            raise ValueError("Kesimpulan pakar tidak boleh kosong")
        if conclusion == inference.conclusion:
            raise ValueError("Kesimpulan baru harus berbeda dari kesimpulan sistem")
        if not conditions:
            raise ValueError("Pilih minimal satu kondisi")
        if not all(c.holds(case) for c in conditions):
            raise ValueError("Semua kondisi harus terpenuhi oleh kasus baru")
        cs = inference.last_true.cornerstone
        if cs is not None and all(c.holds(cs) for c in conditions):
            raise ValueError("Kondisi harus membedakan kasus baru dari kasus kunci "
                             "rule yang dianulir (minimal satu kondisi tidak terpenuhi kasus kunci)")

        rule = Rule(self._next_id, list(conditions), conclusion, dict(case))
        self._next_id += 1
        parent = inference.last_visited
        if parent.matches(case):   # parent == last_true -> perkecualian
            parent.true_child = rule
        else:                      # parent tidak terpenuhi -> jalur false
            parent.false_child = rule
        self.cases.append({"case": dict(case), "conclusion": conclusion})
        return rule

    def confirm_case(self, case: Case, conclusion: str) -> None:
        self.cases.append({"case": dict(case), "conclusion": conclusion})

    def inconsistent_cases(self) -> list[tuple[dict, str]]:
        """Kasus lama yang kesimpulannya kini berbeda dari yang disetujui pakar."""
        bad = []
        for entry in self.cases:
            now = self.infer(entry["case"]).conclusion
            if now != entry["conclusion"]:
                bad.append((entry, now))
        return bad

    # ------------------------------------- informasi baru dari pakar (skema)
    def add_attribute(self, attr: Attribute) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", attr.name or ""):
            raise ValueError("Nama atribut: huruf kecil/angka/underscore, diawali huruf (mis. warna_laptop)")
        if attr.name in self.attributes:
            raise ValueError(f"Atribut '{attr.name}' sudah ada")
        if attr.kind == "categorical":
            opts = list(dict.fromkeys(o.strip() for o in attr.options if o.strip()))
            if len(opts) < 2:
                raise ValueError("Atribut kategorikal minimal punya 2 opsi")
            attr.options = opts
        elif attr.kind == "numeric":
            if not attr.min < attr.max:
                raise ValueError("Nilai minimum harus lebih kecil dari maksimum")
            if attr.step <= 0:
                raise ValueError("Step harus > 0")
            if attr.default is None or not attr.min <= attr.default <= attr.max:
                attr.default = attr.min
        else:
            raise ValueError("Tipe atribut harus numeric atau categorical")
        self.attributes[attr.name] = attr

    def add_option(self, attr: str, option: str) -> None:
        a = self.attributes.get(attr)
        if a is None or a.kind != "categorical":
            raise ValueError("Pilih atribut kategorikal")
        option = option.strip()
        if not option:
            raise ValueError("Opsi tidak boleh kosong")
        if option in a.options:
            raise ValueError(f"Opsi '{option}' sudah ada")
        a.options.append(option)

    def conclusions(self) -> list[str]:
        return sorted({r.conclusion for r in self.rules()})

    def rename_conclusion(self, old: str, new: str) -> None:
        """Perbaiki teks rekomendasi di semua rule dan riwayat kasus."""
        new = new.strip()
        if old not in self.conclusions():
            raise ValueError("Rekomendasi lama tidak ditemukan")
        if not new:
            raise ValueError("Teks baru tidak boleh kosong")
        if new != old and new in self.conclusions():
            raise ValueError("Teks tersebut sudah dipakai rekomendasi lain")
        for r in self.rules():
            if r.conclusion == old:
                r.conclusion = new
        for e in self.cases:
            if e["conclusion"] == old:
                e["conclusion"] = new

    # ------------------------------------------------------------ utilitas
    def rules(self) -> list[Rule]:
        out, stack = [], [self.root]
        while stack:
            r = stack.pop()
            out.append(r)
            for ch in (r.false_child, r.true_child):
                if ch:
                    stack.append(ch)
        return sorted(out, key=lambda r: r.id)

    def to_dot(self, highlight: Optional[set[int]] = None) -> str:
        highlight = highlight or set()
        esc = lambda s: str(s).replace('"', '\\"')
        L = ["digraph RDR {", "rankdir=TB;",
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];']
        for r in self.rules():
            cond = " AND\\n".join(esc(c) for c in r.conditions) or "true"
            label = f"R{r.id}\\nIF {cond}\\nTHEN {esc(r.conclusion)}"
            color = "#ffe08a" if r.id in highlight else "#eef2f7"
            L.append(f'R{r.id} [label="{label}", fillcolor="{color}"];')
            if r.true_child:
                L.append(f'R{r.id} -> R{r.true_child.id} [label="ya (perkecualian)", color="#2e7d32", fontsize=9];')
            if r.false_child:
                L.append(f'R{r.id} -> R{r.false_child.id} [label="tidak", style=dashed, color="#c62828", fontsize=9];')
        L.append("}")
        return "\n".join(L)

    def to_text(self) -> str:
        """Pohon dalam bentuk teks (ya = true-child/perkecualian, tidak = false-child)."""
        line = lambda r: f"R{r.id}: IF {r.describe()} THEN {r.conclusion}"
        out = [line(self.root)]

        def walk(r: Rule, prefix: str) -> None:
            kids = [(lbl, c) for lbl, c in (("ya", r.true_child), ("tidak", r.false_child)) if c]
            for i, (lbl, c) in enumerate(kids):
                last = i == len(kids) - 1
                out.append(f"{prefix}{'└─' if last else '├─'} {lbl}: {line(c)}")
                walk(c, prefix + ("   " if last else "│  "))

        walk(self.root, "")
        return "\n".join(out)

    def to_svg(self, highlight: Optional[set[int]] = None) -> str:
        """Gambar pohon sebagai SVG murni (tanpa Graphviz): kotak rule + garis + label ya/tidak."""
        import html
        import textwrap
        highlight = highlight or set()
        W, GAPX, GAPY, LH, PAD, WRAP = 270, 30, 70, 15, 8, 36

        def lines_of(r: Rule) -> list[str]:
            return ([f"R{r.id}"] + (textwrap.wrap("IF " + r.describe(), WRAP) or ["IF"]) +
                    (textwrap.wrap("THEN " + r.conclusion, WRAP) or ["THEN"]))

        pos: dict[int, tuple[float, int]] = {}
        leaf = [0]

        def layout(r: Rule, d: int) -> float:
            kids = [c for c in (r.true_child, r.false_child) if c]
            if not kids:
                x = leaf[0] * (W + GAPX) + (W + GAPX) / 2
                leaf[0] += 1
            else:
                xs = [layout(c, d + 1) for c in kids]
                x = sum(xs) / len(xs)
            pos[r.id] = (x, d)
            return x

        layout(self.root, 0)
        rules = self.rules()
        H = max(len(lines_of(r)) for r in rules) * LH + 2 * PAD
        maxd = max(d for _, d in pos.values())
        width = max(leaf[0], 1) * (W + GAPX)
        height = (maxd + 1) * (H + GAPY) - GAPY + 20
        top = lambda d: 10 + d * (H + GAPY)

        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
               f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="sans-serif" font-size="12">']
        for r in rules:  # garis dulu, supaya berada di belakang kotak
            px, pd = pos[r.id]
            for child, lbl, color, dash in ((r.true_child, "ya", "#4caf50", ""),
                                            (r.false_child, "tidak", "#ef5350", ' stroke-dasharray="6 4"')):
                if not child:
                    continue
                cx, cd = pos[child.id]
                y1, y2 = top(pd) + H, top(cd)
                out.append(f'<path d="M{px:.0f},{y1} L{cx:.0f},{y2}" stroke="{color}" stroke-width="2" '
                           f'fill="none"{dash}/>')
                out.append(f'<text x="{(px + cx) / 2 + 6:.0f}" y="{(y1 + y2) / 2 + 4:.0f}" fill="{color}" '
                           f'font-weight="bold">{lbl}</text>')
        for r in rules:
            x, d = pos[r.id]
            fill = "#ffe08a" if r.id in highlight else "#eef2f7"
            out.append(f'<rect x="{x - W / 2:.0f}" y="{top(d)}" width="{W}" height="{H}" rx="8" '
                       f'fill="{fill}" stroke="#607d8b" stroke-width="1.5"/>')
            for i, t in enumerate(lines_of(r)):
                weight = ' font-weight="bold"' if i == 0 else ""
                out.append(f'<text x="{x - W / 2 + PAD:.0f}" y="{top(d) + PAD + LH * (i + 1) - 3}" '
                           f'fill="#111"{weight}>{html.escape(t)}</text>')
        out.append("</svg>")
        return "\n".join(out)

    # ---------------------------------------------------------- persistensi
    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "attributes": [asdict(a) for a in self.attributes.values()],
            "next_id": self._next_id,
            "root": self.root.to_dict(),
            "cases": self.cases,
        }

    @staticmethod
    def from_dict(d: dict) -> "KnowledgeBase":
        kb = KnowledgeBase([Attribute(**a) for a in d["attributes"]],
                           d["root"]["conclusion"], d.get("domain", "RDR"))
        kb.root = Rule.from_dict(d["root"])
        kb._next_id = d["next_id"]
        kb.cases = d.get("cases", [])
        return kb

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                              encoding="utf-8")

    @staticmethod
    def load(path: str | Path) -> "KnowledgeBase":
        return KnowledgeBase.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
