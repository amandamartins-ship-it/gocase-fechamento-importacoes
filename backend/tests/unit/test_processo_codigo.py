import pytest

from app.domain.processo_codigo import processo_base


@pytest.mark.parametrize(
    "codigo,esperado",
    [
        ("GOC25129", "GOC25129"),
        ("GOC25129.1", "GOC25129"),
        ("BBI25167.2", "BBI25167"),
        ("GOC25129.10", "GOC25129"),
    ],
)
def test_processo_base(codigo, esperado):
    assert processo_base(codigo) == esperado
