from datetime import date
from decimal import Decimal

from app.application.use_cases.gerar_linhas_rateio import GerarLinhasRazaoRateadoUseCase
from app.domain.entities import LancamentoRazao, StatusFechamento

MES = date(2026, 6, 1)


class RazaoRepoFalso:
    def __init__(self, lancamentos):
        self._lancamentos = lancamentos

    def listar_todos(self, mes_referencia):
        return self._lancamentos


class AuditoriaRepoFalso:
    def __init__(self, memorias=None):
        self._memorias = memorias or {}

    def buscar(self, referencia_tipo, referencia_id):
        return self._memorias.get(referencia_id)


class FechamentoRepoFalso:
    def __init__(self, status_por_processo):
        self._status = status_por_processo

    def buscar(self, processo_codigo, mes_referencia):
        status = self._status.get(processo_codigo)
        if status is None:
            return None
        return type("R", (), {"status": status})()


def _lancamento(id_, historico, processos, debito="0", credito="0", rateio_aplicado=False, data=None):
    return LancamentoRazao(
        id=id_,
        mes_referencia=MES,
        data=data or date(2026, 6, 15),
        historico=historico,
        valor_debito=Decimal(debito),
        valor_credito=Decimal(credito),
        empresa="BB",
        conta_contabil="113103",
        numero_contabil="NR: 000001",
        unidade="50001",
        processos_codigos=processos,
        rateio_aplicado=rateio_aplicado,
    )


def test_lancamento_de_processo_unico_gera_uma_linha_com_valor_cheio():
    lancamento = _lancamento(1, "PGTO FRETE GOC25129.1", ["GOC25129.1"], debito="100")
    use_case = GerarLinhasRazaoRateadoUseCase(
        RazaoRepoFalso([lancamento]), AuditoriaRepoFalso(), FechamentoRepoFalso({"GOC25129": StatusFechamento.FECHADO})
    )

    linhas = use_case.executar(MES)

    assert len(linhas) == 1
    linha = linhas[0]
    assert linha.processo == "GOC25129.1"
    assert linha.processo_full == "GOC25129"
    assert linha.debito == Decimal("100")
    assert linha.movimentacao == Decimal("100")
    assert linha.processo_controle_importacao == "GOC25129-1"
    assert linha.status == str(StatusFechamento.FECHADO)


def test_lancamento_multi_processo_rateado_gera_uma_linha_por_participante():
    lancamento = _lancamento(
        2,
        "PGTO NUMERARIO GOC25129.1, BBI25167.1",
        ["GOC25129.1", "BBI25167.1"],
        debito="1500",
        rateio_aplicado=True,
    )
    memoria = {
        2: {
            "participantes": [
                {"processo": "GOC25129", "valor_debito_destinado": "1000", "valor_credito_destinado": "0"},
                {"processo": "BBI25167", "valor_debito_destinado": "500", "valor_credito_destinado": "0"},
            ]
        }
    }
    use_case = GerarLinhasRazaoRateadoUseCase(
        RazaoRepoFalso([lancamento]),
        AuditoriaRepoFalso(memoria),
        FechamentoRepoFalso({"GOC25129": StatusFechamento.PENDENTE, "BBI25167": StatusFechamento.FECHADO}),
    )

    linhas = use_case.executar(MES)

    assert len(linhas) == 2
    por_processo = {l.processo_full: l for l in linhas}
    assert por_processo["GOC25129"].debito == Decimal("1000")
    assert por_processo["GOC25129"].processo == "GOC25129.1"  # mantém o código específico citado
    assert por_processo["GOC25129"].status == str(StatusFechamento.PENDENTE)
    assert por_processo["BBI25167"].debito == Decimal("500")
    assert por_processo["BBI25167"].status == str(StatusFechamento.FECHADO)


def test_lancamento_multi_processo_sem_rateio_aplicado_nao_gera_linha():
    lancamento = _lancamento(3, "PGTO NUMERARIO GOC25129, BBI25167", ["GOC25129", "BBI25167"], debito="1000")
    use_case = GerarLinhasRazaoRateadoUseCase(
        RazaoRepoFalso([lancamento]), AuditoriaRepoFalso(), FechamentoRepoFalso({})
    )

    assert use_case.executar(MES) == []


def test_processo_sem_fechamento_processado_fica_com_status_explicito():
    lancamento = _lancamento(4, "PGTO FRETE GOC99999", ["GOC99999"], debito="10")
    use_case = GerarLinhasRazaoRateadoUseCase(
        RazaoRepoFalso([lancamento]), AuditoriaRepoFalso(), FechamentoRepoFalso({})
    )

    linhas = use_case.executar(MES)
    assert linhas[0].status == "Sem fechamento processado"


def test_lancamento_sem_processo_e_ignorado():
    lancamento = _lancamento(5, "TARIFA BANCARIA", [], debito="5")
    use_case = GerarLinhasRazaoRateadoUseCase(
        RazaoRepoFalso([lancamento]), AuditoriaRepoFalso(), FechamentoRepoFalso({})
    )
    assert use_case.executar(MES) == []
