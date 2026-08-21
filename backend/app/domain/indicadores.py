"""Cálculo dos indicadores do dashboard - função pura, reusada tanto logo
após processar o fechamento do mês quanto numa leitura posterior (sem
reprocessar nada), para as duas fórmulas nunca divergirem."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import ItemComposicao, ResultadoFechamento, StatusFechamento


@dataclass
class IndicadoresDashboard:
    total_processos: int = 0
    processos_fechados: int = 0
    processos_pendentes: int = 0
    processos_bloqueados: int = 0
    valor_total_contabilizado: Decimal = Decimal("0")
    valor_total_rateado: Decimal = Decimal("0")
    valor_pendente: Decimal = Decimal("0")
    total_variacao_cambial: Decimal = Decimal("0")
    percentual_automacao: Decimal = Decimal("0")
    indice_qualidade_fechamento: Decimal = Decimal("0")


def calcular_indicadores(
    itens: list[tuple[ResultadoFechamento, list[ItemComposicao]]],
) -> IndicadoresDashboard:
    indicadores = IndicadoresDashboard(total_processos=len(itens))

    for resultado, composicao_itens in itens:
        indicadores.valor_total_contabilizado += sum(
            (abs(i.valor_contabilizado) for i in composicao_itens), Decimal("0")
        )
        indicadores.valor_total_rateado += sum((i.valor_rateado for i in composicao_itens), Decimal("0"))

        if resultado.status == StatusFechamento.FECHADO:
            indicadores.processos_fechados += 1
        elif resultado.status == StatusFechamento.PENDENTE:
            indicadores.processos_pendentes += 1
            indicadores.valor_pendente += abs(resultado.saldo_final)
        else:
            indicadores.processos_bloqueados += 1

        if resultado.variacao_cambial:
            indicadores.total_variacao_cambial += resultado.variacao_cambial

    if indicadores.total_processos:
        total = Decimal(indicadores.total_processos)
        # % automação: processos que fecharam sem nenhuma intervenção manual.
        indicadores.percentual_automacao = (Decimal(indicadores.processos_fechados) / total) * 100
        # índice de qualidade: crédito parcial a pendências (correção simples, não bloqueante),
        # nenhum crédito a bloqueios (falta de base documental).
        indicadores.indice_qualidade_fechamento = (
            (Decimal(indicadores.processos_fechados) + Decimal(indicadores.processos_pendentes) * Decimal("0.5"))
            / total
        ) * 100

    return indicadores
