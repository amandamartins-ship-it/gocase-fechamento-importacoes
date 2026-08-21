from datetime import date
from decimal import Decimal

from app.application.use_cases.aplicar_rateio import AplicarRateioUseCase
from app.domain.entities import LancamentoRazao, MatrizRateio, RateioParticipante


class RazaoRepoFalso:
    def __init__(self, lancamentos):
        self._lancamentos = lancamentos
        self.marcados = []

    def listar_multi_processo_pendentes(self, mes_referencia):
        return self._lancamentos

    def marcar_rateio_aplicado(self, lancamento_id):
        self.marcados.append(lancamento_id)

    def salvar_lote(self, lancamentos):
        raise NotImplementedError

    def listar_por_processo(self, processo_codigo, mes_referencia):
        raise NotImplementedError


class RateioBuilderFalso:
    """Simula o Controle de Importações: GOC25129 e BBI25167 compartilham a NF
    '5876' com quantidades 1000/500; GOC99999 não compartilha NF com ninguém."""

    def nfs_do_processo(self, processo_codigo):
        return {"GOC25129": {"5876"}, "BBI25167": {"5876", "1111"}, "GOC99999": set()}.get(processo_codigo, set())

    def construir(self, processos_codigos, nf_referencia):
        if set(processos_codigos) == {"GOC25129", "BBI25167"} and nf_referencia == "5876":
            return MatrizRateio(
                nf_referencia="5876",
                qtd_itens_total_nf=1500,
                participantes=[
                    RateioParticipante("GOC25129", 1000, Decimal("1000") / Decimal("1500"), Decimal("0")),
                    RateioParticipante("BBI25167", 500, Decimal("500") / Decimal("1500"), Decimal("0")),
                ],
                fonte="Controle PIs",
            )
        return None


class RateioRepoFalso:
    def __init__(self):
        self.salvos = []

    def salvar_participante(self, processo_codigo, nf_referencia, qtd_itens_processo, qtd_itens_total_nf, percentual, fonte):
        self.salvos.append((processo_codigo, nf_referencia, qtd_itens_processo, qtd_itens_total_nf, percentual, fonte))


class AuditoriaRepoFalso:
    def __init__(self):
        self.registros = {}

    def registrar(self, referencia_tipo, referencia_id, memoria):
        self.registros[(referencia_tipo, referencia_id)] = memoria

    def buscar(self, referencia_tipo, referencia_id):
        return self.registros.get((referencia_tipo, referencia_id))


def _lancamento(id_, processos, debito="1000.00", credito="0.00"):
    return LancamentoRazao(
        id=id_,
        mes_referencia=date(2026, 6, 1),
        historico=f"PAGTO RATEADO {' '.join(processos)}",
        valor_debito=Decimal(debito),
        valor_credito=Decimal(credito),
        processos_codigos=processos,
    )


def test_aplica_rateio_com_nf_comum_encontrada():
    lancamento = _lancamento(1, ["GOC25129", "BBI25167"])
    razao_repo = RazaoRepoFalso([lancamento])
    rateio_repo = RateioRepoFalso()
    auditoria_repo = AuditoriaRepoFalso()
    use_case = AplicarRateioUseCase(razao_repo, RateioBuilderFalso(), rateio_repo, auditoria_repo)

    resumo = use_case.executar(date(2026, 6, 1))

    assert resumo.total_lancamentos_multi_processo == 1
    assert resumo.aplicados == 1
    assert resumo.pendentes == 0
    assert razao_repo.marcados == [1]
    assert len(rateio_repo.salvos) == 2  # 1 por processo participante

    memoria = auditoria_repo.buscar("rateio_lancamento", 1)
    assert memoria["nf_utilizada"] == "5876"
    valores = {p["processo"]: p for p in memoria["participantes"]}
    assert valores["GOC25129"]["valor_debito_destinado"] == str(Decimal("1000.00") * Decimal("1000") / Decimal("1500"))
    assert valores["BBI25167"]["valor_debito_destinado"] == str(Decimal("1000.00") * Decimal("500") / Decimal("1500"))


def test_pendente_quando_nenhuma_nf_comum():
    lancamento = _lancamento(2, ["GOC25129", "GOC99999"])
    razao_repo = RazaoRepoFalso([lancamento])
    use_case = AplicarRateioUseCase(razao_repo, RateioBuilderFalso(), RateioRepoFalso(), AuditoriaRepoFalso())

    resumo = use_case.executar(date(2026, 6, 1))

    assert resumo.aplicados == 0
    assert resumo.pendentes == 1
    assert razao_repo.marcados == []
    assert "Nenhuma Nota Fiscal em comum" in resumo.motivos_pendencia[0]["motivo"]


def test_pendente_quando_nf_ambigua():
    # BBI25167 sozinho tem 2 NFs possíveis; combinado com GOC25129 (que só tem "5876")
    # o resultado deveria convergir para 1 NF só - testar o caso real de ambiguidade
    # adicionando um terceiro processo fake que force 2 NFs em comum.
    class BuilderAmbiguo(RateioBuilderFalso):
        def nfs_do_processo(self, processo_codigo):
            return {"A": {"111", "222"}, "B": {"111", "222"}}.get(processo_codigo, set())

    lancamento = _lancamento(3, ["A", "B"])
    razao_repo = RazaoRepoFalso([lancamento])
    use_case = AplicarRateioUseCase(razao_repo, BuilderAmbiguo(), RateioRepoFalso(), AuditoriaRepoFalso())

    resumo = use_case.executar(date(2026, 6, 1))

    assert resumo.pendentes == 1
    assert "Mais de uma Nota Fiscal em comum" in resumo.motivos_pendencia[0]["motivo"]


def test_nao_reaplica_rateio_ja_marcado_pois_repo_ja_filtra_pendentes():
    # listar_multi_processo_pendentes já é responsável por só devolver lançamentos
    # com rateio_aplicado=False - o use case não precisa checar de novo.
    razao_repo = RazaoRepoFalso([])
    use_case = AplicarRateioUseCase(razao_repo, RateioBuilderFalso(), RateioRepoFalso(), AuditoriaRepoFalso())
    resumo = use_case.executar(date(2026, 6, 1))
    assert resumo.total_lancamentos_multi_processo == 0
    assert resumo.aplicados == 0
