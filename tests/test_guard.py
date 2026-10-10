from dor.copilot.ledger import Ledger
from dor.copilot.guard import check


def mk():
    L = Ledger("t")
    return L, L.num("a", 12, "settlements", "test"), L.num("b", 34.0, "km", "test", decimals=1)


def test_valid_passes():
    L, a, b = mk()
    assert check(f"There are {a} places. The road is {b} km long.", L)[0]


def test_invented_number_fails():
    L, a, b = mk()
    assert not check(f"There are {a} places and 99 are cut off.", L)[0]


def test_uncited_number_fails():
    L, a, b = mk()
    assert not check("There are 12 places.", L)[0]


def test_wrong_citation_fails():
    L, a, b = mk()
    assert not check(f"The road is 12 km long {b}.", L)[0]


def test_unknown_id_fails():
    L, a, b = mk()
    assert not check("There are 12 places [L099].", L)[0]


def test_protected_names_ignored():
    L, a, b = mk()
    assert check(f"Ward 5 has {a} places.", L, protected=["Ward 5"])[0]


def test_number_word_needs_a_cited_source():
    L, a, b = mk()
    assert not check(f"Two unnamed hamlets are listed {a}.", L)[0]
    L2 = Ledger("t")
    ref = L2.fixed("x", "Nine non-flood pairs", "t")
    tag = ref[ref.rindex("["):]
    assert check(f"Compared with nine pairs {tag}.", L2)[0]

