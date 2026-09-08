import pytest

from ide.app import _demo_case_passed, compile_source
from ide.demo_cases import DEMO_CASES


@pytest.mark.parametrize("case", DEMO_CASES, ids=[case.id for case in DEMO_CASES])
def test_demo_case_matches_expectation(case):
    result = compile_source(case.source)

    assert _demo_case_passed(case, result), (
        f"Caso de demo '{case.id}' no cumplió lo esperado. "
        f"Errores obtenidos: {result['errors']}"
    )


def test_demo_case_ids_are_unique():
    ids = [case.id for case in DEMO_CASES]
    assert len(ids) == len(set(ids))
