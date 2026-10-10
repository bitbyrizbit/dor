RULES = [
    ("how_sure", ("sure", "certain", "confiden", "reliab", "trust", "accura", "uncertain")),
    ("cannot_see", ("cannot see", "can't see", "not see", "blind", "limit", "miss", "unable")),
    ("check_first", ("check first", "verify", "priorit", "inspect", "survey", "first")),
    ("cut_off", ("cut off", "isolat", "villages", "settlement", "stranded", "reach")),
]


def route(question):
    q = question.lower()
    for name, kws in RULES:
        if any(k in q for k in kws):
            return name
    return None
