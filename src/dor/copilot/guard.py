import re

SENT = re.compile(r"(?<=[.!?\u0964])\s+|\n+")
CITE = re.compile(r"\[(L\d{3}(?:\s*,\s*L\d{3})*)\]")
NUM = re.compile(r"\d+(?:[.,]\d+)*")
DEV = {0x0966 + i: str(i) for i in range(10)}


def check(text, ledger, protected=()):
    """Every number in a sentence must appear in a ledger entry cited in that same sentence."""
    for p in sorted(protected, key=len, reverse=True):
        text = text.replace(p, " ")
    text = text.translate(DEV)
    problems = []
    for sent in SENT.split(text):
        s = sent.strip()
        if not s:
            continue
        ids = [x.strip() for m in CITE.findall(s) for x in m.split(",")]
        nums = NUM.findall(CITE.sub(" ", s))
        if not nums:
            continue
        allowed = set()
        for i in ids:
            e = ledger.entries.get(i)
            if e is None:
                problems.append((s, f"unknown id {i}"))
                continue
            allowed.add(e["text"])
            allowed.update(NUM.findall(e["text"]))
        missing = [n for n in nums if n not in allowed]
        if missing:
            problems.append((s, f"numbers not in the cited entries: {missing}"))
    return len(problems) == 0, problems
