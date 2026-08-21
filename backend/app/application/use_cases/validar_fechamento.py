from datetime import date
from decimal import Decimal

from app.application.use_cases.montar_composicao import ResultadoComposicao
from app.domain.entities import Processo, ResultadoFechamento, StatusFechamento, TipoDocumento

DOCUMENTOS_DI = {TipoDocumento.DI}
DOCUMENTOS_INVOICE = {TipoDocumento.INVOICE_CI}
DOCUMENTOS_NF = {TipoDocumento.NOTA_FISCAL, TipoDocumento.XML_NFE}


class ValidarFechamentoUseCase:
    """Decide Fechado/Pendente/Bloqueado - nunca em cima de um "achismo": todo
    motivo de pendência/bloqueio vira uma frase explícita em motivos_pendencia.

    Bloqueado = falta uma base documental essencial (não dá nem para avaliar
    o processo). Pendente = documentos existem, mas o rateio ainda não foi
    aplicado a algum lançamento ou o saldo não fechou além da tolerância de
    variação cambial. Fechado = nada disso acontece."""

    def __init__(self, tolerancia_variacao_cambial: Decimal):
        self._tolerancia = tolerancia_variacao_cambial

    def executar(
        self, processo: Processo, resultado_composicao: ResultadoComposicao, mes_referencia: date
    ) -> ResultadoFechamento:
        motivos: list[str] = []

        tipos_presentes = {doc.tipo for embarque in processo.embarques for doc in embarque.documentos}
        if not (tipos_presentes & DOCUMENTOS_DI):
            motivos.append("DI/DUIMP não localizada entre os documentos do processo.")
        if not (tipos_presentes & DOCUMENTOS_INVOICE):
            motivos.append("Invoice (CI/PI) não localizada entre os documentos do processo.")
        if not (tipos_presentes & DOCUMENTOS_NF):
            motivos.append("Nota Fiscal não localizada entre os documentos do processo.")
        documentos_ausentes = bool(motivos)

        motivos.extend(resultado_composicao.pendencias_rateio)
        rateio_pendente = bool(resultado_composicao.pendencias_rateio)

        saldo = resultado_composicao.saldo_final
        valor_base = sum(
            (abs(item.valor_contabilizado) for item in resultado_composicao.composicao.itens), Decimal("0")
        ) or Decimal("1")
        dentro_da_tolerancia = abs(saldo) <= (valor_base * self._tolerancia)
        variacao_cambial = saldo if (saldo != 0 and dentro_da_tolerancia) else None
        saldo_fora_da_tolerancia = saldo != 0 and not dentro_da_tolerancia

        if saldo_fora_da_tolerancia:
            percentual = abs(saldo) / valor_base * 100
            motivos.append(
                f"Saldo do processo não fechou: R$ {saldo:.2f} ({percentual:.2f}% do valor contabilizado, "
                f"acima da tolerância de {self._tolerancia * 100:.1f}% de variação cambial)."
            )

        if documentos_ausentes:
            status = StatusFechamento.BLOQUEADO
        elif rateio_pendente or saldo_fora_da_tolerancia:
            status = StatusFechamento.PENDENTE
        else:
            status = StatusFechamento.FECHADO

        return ResultadoFechamento(
            processo_codigo=processo.codigo,
            mes_referencia=mes_referencia,
            status=status,
            saldo_final=saldo,
            variacao_cambial=variacao_cambial,
            motivos_pendencia=motivos,
        )
