from datetime import date
from decimal import Decimal

from app.application.use_cases.montar_composicao import MontarComposicaoUseCase
from app.domain.entities import CategoriaLancamento, Documento, DocumentoRef, LancamentoRazao, TipoDocumento


class RazaoRepoFalso:
    def __init__(self, lancamentos):
        self._lancamentos = lancamentos

    def listar_por_processo(self, processo_codigo, mes_referencia):
        return self._lancamentos


class AuditoriaRepoFalso:
    def __init__(self, memorias=None):
        self._memorias = memorias or {}

    def buscar(self, referencia_tipo, referencia_id):
        return self._memorias.get(referencia_id)

    def registrar(self, referencia_tipo, referencia_id, memoria):
        self._memorias[referencia_id] = memoria


def _lancamento(id_, processos, categoria, debito="0", credito="0", rateio_aplicado=False):
    return LancamentoRazao(
        id=id_,
        mes_referencia=date(2026, 6, 1),
        historico="hist",
        valor_debito=Decimal(debito),
        valor_credito=Decimal(credito),
        processos_codigos=processos,
        categoria_classificada=categoria,
        rateio_aplicado=rateio_aplicado,
    )


def test_lancamento_de_processo_unico_e_totalmente_contabilizado():
    lancamentos = [_lancamento(1, ["GOC25129"], CategoriaLancamento.FRETE, debito="100")]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1))

    assert resultado.saldo_final == Decimal("100")
    assert resultado.pendencias_rateio == []
    item = resultado.composicao.itens[0]
    assert item.categoria == CategoriaLancamento.FRETE
    assert item.valor_contabilizado == Decimal("100")
    assert item.valor_rateado == Decimal("0")


def test_lancamento_multi_processo_rateado_usa_valor_da_memoria_de_auditoria():
    lancamentos = [
        _lancamento(2, ["GOC25129", "BBI25167"], CategoriaLancamento.NUMERARIO, debito="1000", rateio_aplicado=True)
    ]
    memoria = {
        2: {
            "participantes": [
                {"processo": "GOC25129", "valor_debito_destinado": "666.67", "valor_credito_destinado": "0"},
                {"processo": "BBI25167", "valor_debito_destinado": "333.33", "valor_credito_destinado": "0"},
            ]
        }
    }
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso(memoria))

    resultado = use_case.executar("GOC25129", date(2026, 6, 1))

    assert resultado.saldo_final == Decimal("666.67")
    assert resultado.pendencias_rateio == []
    item = resultado.composicao.itens[0]
    assert item.valor_contabilizado == Decimal("666.67")
    assert item.valor_rateado == Decimal("666.67")


def test_lancamento_multi_processo_sem_rateio_aplicado_vira_pendencia_e_nao_soma():
    lancamentos = [
        _lancamento(3, ["GOC25129", "BBI25167"], CategoriaLancamento.NUMERARIO, debito="1000", rateio_aplicado=False)
    ]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1))

    assert resultado.saldo_final == Decimal("0")
    assert resultado.composicao.itens == []
    assert len(resultado.pendencias_rateio) == 1
    assert "rateio ainda não foi aplicado" in resultado.pendencias_rateio[0]


def test_processo_sem_categoria_classificada_cai_em_outras_despesas():
    lancamentos = [_lancamento(4, ["GOC25129"], None, debito="50")]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1))

    assert resultado.composicao.itens[0].categoria == CategoriaLancamento.OUTRAS_DESPESAS


def test_saldo_final_soma_debito_menos_credito_de_varias_categorias():
    lancamentos = [
        _lancamento(5, ["GOC25129"], CategoriaLancamento.FRETE, debito="100"),
        _lancamento(6, ["GOC25129"], CategoriaLancamento.REEMBOLSO, credito="30"),
    ]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1))

    assert resultado.saldo_final == Decimal("70")


def _documento(tipo, valor_extraido):
    return Documento(
        ref=DocumentoRef(drive_file_id=f"file-{tipo}", nome_arquivo=f"{tipo}.pdf", caminho="x"),
        tipo=tipo,
        valor_extraido=Decimal(valor_extraido) if valor_extraido is not None else None,
    )


def test_valor_documentos_e_diferenca_cruzam_com_o_ja_contabilizado():
    lancamentos = [_lancamento(7, ["GOC25129"], CategoriaLancamento.ARMAZENAGEM, debito="700")]
    documentos = [_documento(TipoDocumento.ARMAZENAGEM, "713.39")]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1), documentos)

    item = resultado.composicao.itens[0]
    assert item.valor_documentos == Decimal("713.39")
    assert item.valor_contabilizado == Decimal("700")
    assert item.diferenca == Decimal("13.39")


def test_categoria_so_documentada_ainda_nao_contabilizada_aparece_com_contabilizado_zero():
    # exatamente o caso "despesas que ainda não foram contabilizadas" pedido pela usuária
    lancamentos: list = []
    documentos = [_documento(TipoDocumento.HONORARIOS, "750.00")]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1), documentos)

    assert len(resultado.composicao.itens) == 1
    item = resultado.composicao.itens[0]
    assert item.categoria == CategoriaLancamento.HONORARIOS
    assert item.valor_contabilizado == Decimal("0")
    assert item.valor_documentos == Decimal("750.00")
    assert item.diferenca == Decimal("750.00")


def test_documento_sem_valor_extraido_ou_sem_categoria_mapeada_e_ignorado():
    lancamentos = [_lancamento(8, ["GOC25129"], CategoriaLancamento.FRETE, debito="100")]
    documentos = [
        _documento(TipoDocumento.NUMERARIO, None),  # ainda não lido
        _documento(TipoDocumento.DI, "999.99"),  # fora do escopo do mapeamento (não é FATURAMENTO FINAL)
    ]
    use_case = MontarComposicaoUseCase(RazaoRepoFalso(lancamentos), AuditoriaRepoFalso())

    resultado = use_case.executar("GOC25129", date(2026, 6, 1), documentos)

    assert len(resultado.composicao.itens) == 1
    assert resultado.composicao.itens[0].valor_documentos == Decimal("0")
