from dor.copilot.ledger import Ledger
from dor.copilot.ask import validate


def mk():
    L = Ledger("t")
    return L, L.num("a", 30, "settlements", "t")


def test_valid_and_refusal():
    L, a = mk()
    assert validate(f"{a} settlements are cut off.", L, [])[0]
    assert validate("NOT_IN_FACTS", L, [])[0]


def test_rejects_invented_number_and_uncited_sentence():
    L, a = mk()
    assert not validate(f"{a} settlements are cut off and 40 are at risk.", L, [])[0]
    assert not validate("Everything is fine.", L, [])[0]
