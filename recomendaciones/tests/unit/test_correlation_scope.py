"""El identificador de correlación que llega de afuera se acepta solo si tiene la forma que usa api-general.

Llega por el encabezado `X-Correlation-ID`, por los eventos del broker y por `recompute:requests`; se devuelve en la
respuesta y se escribe en cada línea de log. Un valor arbitrario (larguísimo, con saltos de línea o caracteres de
control) se reemplaza por uno generado, igual que cuando falta.
"""

from __future__ import annotations

import pytest

from recomendaciones.observability.logging import correlation_scope


@pytest.mark.parametrize(
    "valor",
    [
        "6f1c0d2e-8a4b-4c3d-9e2f-0a1b2c3d4e5f",
        "a" * 128,
        "req.42:abc_DEF-9",
    ],
)
def test_un_identificador_valido_se_conserva(valor: str) -> None:
    with correlation_scope(valor) as efectivo:
        assert efectivo == valor


@pytest.mark.parametrize(
    "valor",
    [
        "a" * 129,
        "x" * 10_000,
        "abc\ndef",
        "abc\r\nSet-Cookie: x=1",
        "abc def",
        "abc\x00def",
        "<script>alert(1)</script>",
        "ñandú",
        "",
        None,
    ],
)
def test_un_identificador_invalido_o_ausente_se_reemplaza(valor: str | None) -> None:
    with correlation_scope(valor) as efectivo:
        assert efectivo != valor
        assert len(efectivo) == 32
        assert efectivo.isalnum()
