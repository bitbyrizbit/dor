import json


class Ledger:
    def __init__(self, run_id=""):
        self.run_id = run_id
        self.entries = {}
        self._by_key = {}

    def _new(self, key, text, unit, source, value):
        if key in self._by_key:
            return self._by_key[key]
        eid = f"L{len(self.entries) + 1:03d}"
        self.entries[eid] = {"id": eid, "key": key, "text": text, "value": value,
                             "unit": unit, "source": source}
        self._by_key[key] = eid
        return eid

    def num(self, key, value, unit="", source="", decimals=None):
        if decimals is None:
            decimals = 0 if float(value).is_integer() else 1
        text = f"{float(value):.{decimals}f}"
        return f"{text} [{self._new(key, text, unit, source, float(value))}]"

    def fixed(self, key, text, source=""):
        return f"{text} [{self._new(key, text, '', source, None)}]"

    def pairs(self):
        return sorted((e["key"], e["text"]) for e in self.entries.values())

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"run_id": self.run_id, "entries": list(self.entries.values())}, f, indent=1)
