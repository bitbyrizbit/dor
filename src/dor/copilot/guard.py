import re

SENT = re.compile(r"(?<=[.!?\u0964])\s+|\n+")
CITE = re.compile(r"\[(L\d{3}(?:\s*,\s*L\d{3})*)\]")
NUM = re.compile(r"\d+(?:[.,]\d+)*")
TOK = re.compile(r"[A-Za-z]+|[\u0900-\u097F]+")
DEV = {0x0966 + i: str(i) for i in range(10)}
VATA = "\u0935\u091f\u093e"
EN_WORDS = set("zero two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
               "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand "
               "million dozen twice double triple".split())
NE_WORDS = {"\u0926\u0941\u0908", "\u0924\u0940\u0928", "\u091a\u093e\u0930", "\u092a\u093e\u0901\u091a",
            "\u0938\u093e\u0924", "\u0906\u0920", "\u0928\u094c", "\u0926\u0936", "\u0926\u0938",
            "\u092c\u0940\u0938", "\u0924\u0940\u0938", "\u0938\u092f", "\u0939\u091c\u093e\u0930", "\u0932\u093e\u0916"}
WORDS = EN_WORDS | NE_WORDS


def _base(w):
    return w[:-len(VATA)] if w.endswith(VATA) and len(w) > len(VATA) else w


def _num_words(text):
    return [w for w in (_base(t.lower()) for t in TOK.findall(text)) if w in WORDS]


def check(text, ledger, protected=()):
    """Every digit string and every number word in a sentence must appear in a ledger entry cited in that sentence."""
    for p in sorted(protected, key=len, reverse=True):
        text = text.replace(p, " ")
    text = text.translate(DEV)
    problems = []
    for sent in SENT.split(text):
        s = sent.strip()
        if not s:
            continue
        ids = [x.strip() for m in CITE.findall(s) for x in m.split(",")]
        body = CITE.sub(" ", s)
        nums, words = NUM.findall(body), _num_words(body)
        if not nums and not words:
            continue
        allowed, allowed_w = set(), set()
        for i in ids:
            e = ledger.entries.get(i)
            if e is None:
                problems.append((s, f"unknown id {i}"))
                continue
            allowed.add(e["text"])
            allowed.update(NUM.findall(e["text"]))
            allowed_w.update(_base(t.lower()) for t in TOK.findall(e["text"]))
        missing = [n for n in nums if n not in allowed]
        missing_w = [w for w in words if w not in allowed_w]
        if missing:
            problems.append((s, f"numbers not in the cited entries: {missing}"))
        if missing_w:
            problems.append((s, f"number words not in the cited entries: {missing_w}"))
    return len(problems) == 0, problems
