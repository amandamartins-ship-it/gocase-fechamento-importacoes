"""Mapeia o TipoDocumento (Fase 2, hoje só confiável para a pasta "FATURAMENTO
FINAL" - já pré-categorizada pela trading) para a CategoriaLancamento usada na
composição contábil (Fase 5). PRESTACAO_CONTAS/DEVOLUCAO_SALDO ficam de fora:
são conceitos de acerto de saldo do numerário, não despesas por si só."""

from app.domain.entities import CategoriaLancamento, TipoDocumento

CATEGORIA_POR_TIPO_DOCUMENTO: dict[TipoDocumento, CategoriaLancamento] = {
    TipoDocumento.FRETE_INTERNACIONAL: CategoriaLancamento.FRETE,
    TipoDocumento.FRETE_ENTREGA: CategoriaLancamento.FRETE,
    TipoDocumento.ARMAZENAGEM: CategoriaLancamento.ARMAZENAGEM,
    TipoDocumento.HONORARIOS: CategoriaLancamento.HONORARIOS,
    TipoDocumento.NUMERARIO: CategoriaLancamento.NUMERARIO,
    TipoDocumento.ICMS: CategoriaLancamento.OUTRAS_DESPESAS,  # mesmo precedente do lancamento_classifier
}


def categoria_do_documento(tipo: TipoDocumento) -> CategoriaLancamento | None:
    return CATEGORIA_POR_TIPO_DOCUMENTO.get(tipo)
