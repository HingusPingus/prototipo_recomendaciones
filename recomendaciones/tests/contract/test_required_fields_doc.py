"""T047 — el documento de campos requeridos cubre lo que los contract tests validan (FR-063).

El documento es el índice que se entrega a `api-general`; si un contract test empieza a exigir un campo que
el documento no nombra, el documento quedó desactualizado y este test lo detecta.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.contract.test_contract_gate import DEP_CHECKS, EVENTS, SYNC_CONSUMER, _required_by_consumer

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "contracts" / "required-fields.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_every_field_the_contract_tests_validate_is_named_in_the_document() -> None:
    doc = _doc()
    fields = set().union(*SYNC_CONSUMER.values())
    for event_type, _parser in EVENTS.values():
        fields |= _required_by_consumer(event_type)
    missing = sorted(f for f in fields if f"`{f}`" not in doc)
    assert not missing, f"campos validados por los contract tests ausentes del documento: {missing}"


def test_every_dependency_and_contract_requirement_is_indexed() -> None:
    doc = _doc()
    for dep in [*DEP_CHECKS, "DEP-3", "DEP-4"]:
        assert re.search(rf"\| {dep} \|", doc), dep
    for n in range(1, 20):
        assert re.search(rf"\| CR-{n} \|", doc), f"CR-{n}"
    assert re.search(r"\| CR-13 \|.*retirada", doc) and re.search(r"\| CR-14 \|.*retirada", doc)
    assert re.search(r"\| DEP-3 \|.*vacante", doc) and re.search(r"\| DEP-4 \|.*resuelta", doc)


def test_document_names_the_most_severe_dependency_and_the_source_of_truth() -> None:
    doc = _doc()
    assert "DEP-10" in doc and "mayor severidad" in doc
    assert "fuente de verdad del contrato es `api-general`" in doc
    assert "FR-079a" in doc


def test_document_is_linked_from_the_readme_and_links_the_contract_tests() -> None:
    assert "docs/contracts/required-fields.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "tests/contract/test_contract_gate.py" in _doc()
