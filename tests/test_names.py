"""Names may use any alphabet's letters and full stops, never a colon (it
separates the kind from the name in an id)."""

from lib.validators import Validators


def test_accents_and_titles_are_names():
    for name in ("Mirela Kostić", "Inês Ferreira-Lund", "Dr. Imelda Strand", "O'Brien", "Søren"):
        assert Validators.validate_name(name) == (True, None), name


def test_colon_and_odd_signs_are_refused():
    ok, error = Validators.validate_name("npc:Mirela")
    assert not ok and ":" in error
    assert not Validators.validate_name("Mirela (boss)")[0]
