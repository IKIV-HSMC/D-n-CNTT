"""
mindmap_engine.py  -  Document JSON  ->  Mindmap + Flashcards (CPU, offline, no API)

Input : JSON do bước trích xuất tạo ra, tối thiểu có khóa "extracted_text".
        (nếu JSON đã có "sections": [{"heading","level","text"}] thì dùng luôn, chính xác hơn)
Output: {"title", "mindmap": {"nodes":[{id,label,parent_id}]}, "flashcards":[{front,back,node_id}], "stats"}

Dùng:  python mindmap_engine.py input.json -o output.json
"""
from __future__ import annotations
import argparse, json, math, re
from collections import Counter
from dataclasses import dataclass, field

# ----------------------------------------------------------------- cấu hình
MAX_KV_NODES = 8          # số nhánh con tối đa mỗi mục
MAX_CARDS_PER_SECTION = 10
LABEL_MAX = 56

BOILER = {"LỜI CẢM ƠN", "LỜI CAM ĐOAN", "DANH MỤC HÌNH ẢNH", "DANH MỤC BẢNG", "MỤC LỤC",
          "DANH MỤC TỪ VIẾT TẮT", "DANH MỤC KÝ HIỆU", "LỜI MỞ ĐẦU", "NHẬN XÉT CỦA GIẢNG VIÊN"}
END_MARKERS = {"TÀI LIỆU THAM KHẢO", "PHỤ LỤC"}
INSTITUTION = ("TỔNG LIÊN ĐOÀN", "TRƯỜNG", "KHOA", "THÀNH PHỐ", "BÁO CÁO", "THIẾT KẾ GIAO DIỆN")

STOP = set("""và là của các những một cho trong để với được có khi theo từ đến này đó không như về hoặc tại
bằng nhưng cũng đã sẽ rất nên mà thì vì nếu hay bởi sau trước trên dưới ra vào lại còn đang cần phải
mỗi mọi nhiều ít cả khác đều chỉ rằng thế nào gì ai đâu""".split())

CAPTION_RE = re.compile(r"^(Hình|Bảng)\s+\d+\s*[\.:]")
TABLE_RE = re.compile(r"\s\|\s")
KV_RE = re.compile(r"^(?:\d+[\.\)]\s*)?(?P<k>[^:：|]{2,70}?)\s*[:：]\s*(?P<v>\S.{12,})$")
SPECIAL = [(re.compile(r"^(PERSONA|Storyboard|Flow)\s*\d+", re.I), 3),
           (re.compile(r"^Cấp\s*\d+\s*:"), 3),
           (re.compile(r"^Empathy Map", re.I), 4)]
SENT_SPLIT = re.compile(r"(?<=[\.\!\?])\s+(?=[A-ZÀ-ỸĐ“\"])")
TOKEN_RE = re.compile(r"[\wÀ-ỹ/\-]+", re.UNICODE)


# ----------------------------------------------------------------- cấu trúc
@dataclass
class Section:
    level: int
    title: str
    kv: list = field(default_factory=list)      # [(label, desc)]
    paras: list = field(default_factory=list)   # [str]
    parent: "Section | None" = None

    def raw_text(self) -> str:
        parts = [f"{k}: {v}" for k, v in self.kv] + self.paras
        return "\n".join(parts)


# ----------------------------------------------------------------- phân tích văn bản
def heading_level(line: str) -> int:
    s = line.strip()
    if not s or len(s) > 110 or s.endswith((".", ";", ",", ":")):
        return 0
    if CAPTION_RE.match(s) or TABLE_RE.search(s) or s[0] in "“\"(-•*":
        return 0
    for pat, lv in SPECIAL:
        if pat.match(s):
            return lv
    if KV_RE.match(s):
        return 0
    words = s.split()
    if len(words) < 2 or len(words) > 16 or not s[0].isupper():
        return 0
    if s.isupper() and len(s) >= 6:
        return 1
    return 2


def parse_sections(text: str) -> list[Section]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # nội dung bắt đầu từ H1 thật đầu tiên sau phần mở đầu (bìa, cảm ơn, danh mục hình/bảng)
    last_boiler = max((i for i, l in enumerate(lines) if l.upper() in BOILER), default=-1)
    start = 0
    for i in range(last_boiler + 1, len(lines)):
        l = lines[i]
        if heading_level(l) == 1 and l.upper() not in BOILER and not l.startswith(INSTITUTION):
            start = i
            break
    sections: list[Section] = []
    stack: list[Section] = []
    skipping = False
    body = lines[start:]
    repeats = Counter(l for l in body if heading_level(l) == 2)
    for l in body:
        up = l.upper()
        if up in END_MARKERS:
            break
        lv = heading_level(l)
        if lv:
            skipping = up in BOILER
            if skipping:
                continue
            if lv == 2 and repeats[l] >= 2 and stack and stack[-1].level >= 3:
                lv = stack[-1].level + 1 if stack[-1].level < 4 else 4
                while stack and stack[-1].level >= lv:
                    stack.pop()
            else:
                while stack and stack[-1].level >= lv:
                    stack.pop()
            sec = Section(level=lv, title=l, parent=stack[-1] if stack else None)
            sections.append(sec)
            stack.append(sec)
            continue
        if skipping or not sections:
            continue
        if CAPTION_RE.match(l) or TABLE_RE.search(l):
            continue
        m = KV_RE.match(l)
        if m and len(m.group("k").split()) <= 10 and not m.group("k").lstrip().startswith(("“", '"')):
            sections[-1].kv.append((m.group("k").strip(), m.group("v").strip()))
        elif len(l) >= 25:
            sections[-1].paras.append(l)
    return sections


def sections_from_json_sections(items: list[dict]) -> list[Section]:
    out, stack = [], []
    for it in items:
        lv = int(it.get("level", 1))
        while stack and stack[-1].level >= lv:
            stack.pop()
        sec = Section(level=lv, title=it["heading"], parent=stack[-1] if stack else None)
        for l in (it.get("text") or "").split("\n"):
            l = l.strip()
            m = KV_RE.match(l)
            if m and len(m.group("k").split()) <= 10:
                sec.kv.append((m.group("k").strip(), m.group("v").strip()))
            elif len(l) >= 25:
                sec.paras.append(l)
        out.append(sec)
        stack.append(sec)
    return out


# ----------------------------------------------------------------- tiện ích NLP nhẹ
def tokens(s: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(s)]


def short(label: str, n: int = LABEL_MAX) -> str:
    s = label.strip().strip("“”\"")
    if len(s) > n:
        s = re.sub(r"\s*\([^)]*\)", "", s)
    if len(s) > n:
        cut = s[:n].rsplit(" ", 1)[0]
        s = cut.rstrip(",;:-– ") + "…"
    return s


def cap(text: str, n: int = 320) -> str:
    if len(text) <= n:
        return text
    cut = text[:n]
    p = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[:p + 1] if p > 120 else cut.rsplit(" ", 1)[0] + "…")


class Idf:
    def __init__(self, docs: list[str]):
        df = Counter()
        for d in docs:
            df.update(set(tokens(d)))
        self.n = max(len(docs), 1)
        self.df = df

    def __call__(self, tok: str) -> float:
        return math.log((1 + self.n) / (1 + self.df.get(tok, 0))) + 1


def best_sentence(paras: list[str], idf: Idf):
    best, best_score = None, 0.0
    for p in paras:
        for s in SENT_SPLIT.split(p):
            tk = [t for t in tokens(s) if t not in STOP]
            if not 8 <= len(tokens(s)) <= 40 or not tk:
                continue
            top = sorted((idf(t) for t in tk), reverse=True)[:5]
            sc = sum(top) / len(top)
            if sc > best_score:
                best, best_score = s.strip(), sc
    return best


def cloze(sentence: str, idf: Idf):
    """Che đi cụm 2 âm tiết có trọng số idf cao nhất -> (câu đã che, đáp án)."""
    words = TOKEN_RE.findall(sentence)
    best, best_sc = None, 0.0
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        la, lb = a.lower(), b.lower()
        if la in STOP or lb in STOP or len(la) < 2 or len(lb) < 2 or la.isdigit() or lb.isdigit():
            continue
        sc = idf(la) + idf(lb)
        if sc > best_sc:
            best, best_sc = (a, b), sc
    if not best:
        return None
    pat = re.compile(re.escape(best[0]) + r"\s+" + re.escape(best[1]), re.I)
    m = pat.search(sentence)
    if not m:
        return None
    return pat.sub("_____", sentence, count=1), m.group(0)


# ----------------------------------------------------------------- dựng mindmap + flashcard
class Builder:
    def __init__(self, idf: Idf):
        self.idf = idf
        self.nodes: list[dict] = []
        self.cards: list[dict] = []
        self._seen = set()

    def node(self, label: str, parent_id: str | None) -> str:
        nid = f"n{len(self.nodes)}"
        self.nodes.append({"id": nid, "label": label, "parent_id": parent_id})
        return nid

    def card(self, front: str, back: str, node_id: str):
        key = front.strip().lower()
        if key in self._seen or len(back.strip()) < 3:
            return
        self._seen.add(key)
        self.cards.append({"front": front.strip(), "back": back.strip(), "node_id": node_id})

    def section(self, sec: Section, parent_id: str) -> str:
        nid = self.node(short(sec.title), parent_id)
        ctx = short(sec.title, 48)
        n_cards = 0
        for k, v in sec.kv:
            if n_cards >= MAX_CARDS_PER_SECTION:
                break
            if sum(1 for n in self.nodes if n["parent_id"] == nid) < MAX_KV_NODES:
                kid = self.node(short(k, 40), nid)
            else:
                kid = nid
            self.card(f"Trong “{ctx}”, “{short(k, 40)}” là gì / nói về điều gì?", cap(v), kid)
            n_cards += 1
        for p in sec.paras:                      # câu định nghĩa: "X là ..."
            for s in SENT_SPLIT.split(p):
                m = re.match(r"^(?P<t>[A-ZĐÀ-Ỹ][^,.:;]{2,45}?)\s+là\s+(?P<d>.{15,})$", s.strip())
                if m and n_cards < MAX_CARDS_PER_SECTION:
                    self.card(f"{m.group('t')} là gì?", cap(s.strip()), nid)
                    n_cards += 1
        if sec.paras and n_cards < MAX_CARDS_PER_SECTION:
            s = best_sentence(sec.paras, self.idf)
            if s:
                cz = cloze(s, self.idf)
                if cz:
                    q, a = cz
                    if not sec.kv:
                        kid = self.node(short(a, 40), nid)    # nhánh từ khóa khi mục không có "nhãn: mô tả"
                    else:
                        kid = nid
                    self.card(f"Điền vào chỗ trống: {cap(q, 260)}", a, kid)
        return nid


def guess_title(text: str, fallback: str) -> str:
    cands = [l.strip() for l in text.split("\n") if l.strip()][:30]
    cands = [l for l in cands if l.isupper() and len(l) > 25 and not l.startswith(INSTITUTION)
             and not re.search(r"\d{4,}", l)]
    return max(cands, key=len) if cands else fallback


def generate(doc: dict | str, title: str | None = None) -> dict:
    if isinstance(doc, str):
        doc = {"extracted_text": doc}
    text = doc.get("extracted_text", "")
    if doc.get("sections"):
        secs = sections_from_json_sections(doc["sections"])
    else:
        secs = parse_sections(text)
    fallback = (doc.get("original_filename") or "Tài liệu").rsplit(".", 1)[0]
    title = title or doc.get("title") or guess_title(text, fallback)

    corpus = [p for s in secs for p in (s.paras + [v for _, v in s.kv])] or [text]
    b = Builder(Idf(corpus))
    root = b.node(short(title, 70), None)
    ids: dict[int, str] = {}
    for s in secs:
        parent = ids.get(id(s.parent), root) if s.parent else root
        ids[id(s)] = b.section(s, parent)

    return {
        "title": title,
        "mindmap": {"nodes": b.nodes},
        "flashcards": b.cards,
        "stats": {"sections": len(secs), "nodes": len(b.nodes), "flashcards": len(b.cards)},
    }


def generate_for_section(sec: Section, idf: Idf) -> dict:
    """Dùng cho tạo dữ liệu huấn luyện theo từng chunk."""
    b = Builder(idf)
    root = b.node(short(sec.title, 70), None)
    for k, v in sec.kv:
        kid = b.node(short(k, 40), root)
        b.card(f"Trong “{short(sec.title, 48)}”, “{short(k, 40)}” là gì / nói về điều gì?", cap(v), kid)
    return {"mindmap": {"nodes": b.nodes}, "flashcards": b.cards}


# ----------------------------------------------------------------- xuất cho React Flow
def to_reactflow(mindmap: dict, dx: int = 280, dy: int = 64) -> dict:
    nodes = mindmap["nodes"]
    kids: dict[str | None, list[dict]] = {}
    for n in nodes:
        kids.setdefault(n["parent_id"], []).append(n)
    pos, row = {}, [0]

    def walk(n, depth):
        ch = kids.get(n["id"], [])
        if not ch:
            y = row[0] * dy
            row[0] += 1
        else:
            ys = [walk(c, depth + 1) for c in ch]
            y = sum(ys) / len(ys)
        pos[n["id"]] = {"x": depth * dx, "y": y}
        return y

    for r in kids.get(None, []):
        walk(r, 0)
    return {
        "nodes": [{"id": n["id"], "data": {"label": n["label"]}, "position": pos[n["id"]]} for n in nodes],
        "edges": [{"id": f"e-{n['parent_id']}-{n['id']}", "source": n["parent_id"], "target": n["id"]}
                  for n in nodes if n["parent_id"]],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="output.json")
    ap.add_argument("--reactflow", help="ghi thêm file nodes/edges cho React Flow")
    a = ap.parse_args()
    out = generate(json.load(open(a.input, encoding="utf-8")))
    json.dump(out, open(a.output, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if a.reactflow:
        json.dump(to_reactflow(out["mindmap"]), open(a.reactflow, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(out["stats"])
