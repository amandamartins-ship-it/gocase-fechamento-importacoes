from decimal import Decimal

from app.application.use_cases.importar_razao import ImportarRazaoUseCase
from app.infrastructure.classification.lancamento_classifier import KeywordLancamentoClassifier
from app.infrastructure.razao.parser import RazaoCsvParser
from tests.unit.test_razao_parser import _csv_bytes


class RepoFalso:
    def __init__(self):
        self.salvos = []

    def salvar_lote(self, lancamentos):
        self.salvos = lancamentos

    def listar_por_processo(self, processo_codigo, mes_referencia):
        return [l for l in self.salvos if processo_codigo in l.processos_codigos]


def test_resumo_conta_lancamentos_multi_processo_e_sem_processo():
    repo = RepoFalso()
    use_case = ImportarRazaoUseCase(RazaoCsvParser(), KeywordLancamentoClassifier(), repo)

    resumo = use_case.executar(_csv_bytes(), "razao.csv")

    assert resumo.total_lancamentos == 4
    assert resumo.lancamentos_sem_processo == 1  # tarifa bancária
    assert resumo.lancamentos_multi_processo == 1  # numerário GOC25129 + BBI25167
    assert resumo.processos_citados == ["BBI25167", "GOC25129"]
    assert resumo.total_valor_debito == Decimal("1234.56") + Decimal("500.00") + Decimal("10.00")
    assert resumo.total_valor_credito == Decimal("12345.67")
    assert len(repo.salvos) == 4  # persistiu via repo.salvar_lote


def test_resumo_classifica_por_categoria():
    repo = RepoFalso()
    use_case = ImportarRazaoUseCase(RazaoCsvParser(), KeywordLancamentoClassifier(), repo)

    resumo = use_case.executar(_csv_bytes(), "razao.csv")

    assert resumo.por_categoria["Frete"] == 1
    assert resumo.por_categoria["Numerário"] == 1
    assert resumo.por_categoria["Honorários"] == 1
    assert resumo.por_categoria["Outras despesas"] == 1  # tarifa bancária
