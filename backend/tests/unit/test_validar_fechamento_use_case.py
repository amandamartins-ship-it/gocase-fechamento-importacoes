from datetime import date
from decimal import Decimal

from app.application.use_cases.montar_composicao import ResultadoComposicao
from app.application.use_cases.validar_fechamento import ValidarFechamentoUseCase
from app.domain.entities import (
    CategoriaLancamento,
    ComposicaoContabil,
    Documento,
    DocumentoRef,
    Embarque,
    ItemComposicao,
    Processo,
    StatusFechamento,
    StatusLeituraDocumento,
    TipoDocumento,
)

MES = date(2026, 6, 1)


def _documento(tipo: TipoDocumento) -> Documento:
    return Documento(
        ref=DocumentoRef(drive_file_id="x", nome_arquivo="x.pdf", caminho="x"),
        tipo=tipo,
        status_leitura=StatusLeituraDocumento.OK,
    )


def _processo_com_documentos(*tipos: TipoDocumento) -> Processo:
    embarque = Embarque(codigo="GOC25129.1", drive_folder_id="f1")
    embarque.documentos = [_documento(t) for t in tipos]
    processo = Processo(codigo="GOC25129", empresa_codigo="GOC")
    processo.embarques = [embarque]
    return processo


def _composicao(saldo: Decimal, valor_contabilizado: Decimal = None) -> ResultadoComposicao:
    valor = valor_contabilizado if valor_contabilizado is not None else abs(saldo)
    itens = [
        ItemComposicao(
            categoria=CategoriaLancamento.FRETE,
            valor_documentos=Decimal("0"),
            valor_contabilizado=valor,
            valor_rateado=Decimal("0"),
            percentual_rateio=None,
            diferenca=Decimal("0"),
        )
    ]
    composicao = ComposicaoContabil(processo_codigo="GOC25129", mes_referencia=MES, itens=itens)
    return ResultadoComposicao(composicao=composicao, saldo_final=saldo, pendencias_rateio=[])


def test_bloqueado_quando_falta_documento_obrigatorio():
    processo = _processo_com_documentos(TipoDocumento.DI)  # falta Invoice e NF
    use_case = ValidarFechamentoUseCase(Decimal("0.02"))

    resultado = use_case.executar(processo, _composicao(Decimal("0")), MES)

    assert resultado.status == StatusFechamento.BLOQUEADO
    assert any("Invoice" in m for m in resultado.motivos_pendencia)
    assert any("Nota Fiscal" in m for m in resultado.motivos_pendencia)


def test_fechado_quando_documentos_completos_e_saldo_zero():
    processo = _processo_com_documentos(TipoDocumento.DI, TipoDocumento.INVOICE_CI, TipoDocumento.NOTA_FISCAL)
    use_case = ValidarFechamentoUseCase(Decimal("0.02"))

    resultado = use_case.executar(processo, _composicao(Decimal("0")), MES)

    assert resultado.status == StatusFechamento.FECHADO
    assert resultado.motivos_pendencia == []
    assert resultado.variacao_cambial is None


def test_xml_nfe_tambem_conta_como_nota_fiscal():
    processo = _processo_com_documentos(TipoDocumento.DI, TipoDocumento.INVOICE_CI, TipoDocumento.XML_NFE)
    use_case = ValidarFechamentoUseCase(Decimal("0.02"))

    resultado = use_case.executar(processo, _composicao(Decimal("0")), MES)

    assert resultado.status == StatusFechamento.FECHADO


def test_pendente_quando_saldo_fora_da_tolerancia():
    processo = _processo_com_documentos(TipoDocumento.DI, TipoDocumento.INVOICE_CI, TipoDocumento.NOTA_FISCAL)
    use_case = ValidarFechamentoUseCase(Decimal("0.02"))
    # saldo de 100 sobre uma base contabilizada de 1000 = 10%, bem acima da tolerância de 2%
    resultado = use_case.executar(processo, _composicao(Decimal("100"), Decimal("1000")), MES)

    assert resultado.status == StatusFechamento.PENDENTE
    assert resultado.variacao_cambial is None
    assert any("não fechou" in m for m in resultado.motivos_pendencia)


def test_fechado_quando_saldo_dentro_da_tolerancia_de_variacao_cambial():
    processo = _processo_com_documentos(TipoDocumento.DI, TipoDocumento.INVOICE_CI, TipoDocumento.NOTA_FISCAL)
    use_case = ValidarFechamentoUseCase(Decimal("0.02"))
    # saldo de 10 sobre uma base de 1000 = 1%, dentro da tolerância de 2%
    resultado = use_case.executar(processo, _composicao(Decimal("10"), Decimal("1000")), MES)

    assert resultado.status == StatusFechamento.FECHADO
    assert resultado.variacao_cambial == Decimal("10")


def test_pendente_quando_ha_pendencia_de_rateio_mesmo_com_documentos_completos():
    processo = _processo_com_documentos(TipoDocumento.DI, TipoDocumento.INVOICE_CI, TipoDocumento.NOTA_FISCAL)
    use_case = ValidarFechamentoUseCase(Decimal("0.02"))
    composicao = _composicao(Decimal("0"))
    composicao.pendencias_rateio.append("Lançamento X cita 2 processos, rateio não aplicado.")

    resultado = use_case.executar(processo, composicao, MES)

    assert resultado.status == StatusFechamento.PENDENTE
    assert "rateio não aplicado" in resultado.motivos_pendencia[0]
