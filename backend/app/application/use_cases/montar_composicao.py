from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.documento_categoria import categoria_do_documento
from app.domain.entities import CategoriaLancamento, ComposicaoContabil, Documento, ItemComposicao
from app.domain.ports import AuditoriaRepository, RazaoRepository
from app.domain.processo_codigo import processo_base


@dataclass
class ResultadoComposicao:
    composicao: ComposicaoContabil
    saldo_final: Decimal
    pendencias_rateio: list[str] = field(default_factory=list)


class MontarComposicaoUseCase:
    """Reconstrói a composição contábil de um processo a partir dos lançamentos
    do Razão já classificados (Fase 3) e rateados (Fase 4), cruzando com o
    valor real extraído dos documentos (Fase 9 - hoje só FATURAMENTO FINAL,
    já escopado a UM processo por construção, sem rateio adicional aqui).
    Quando um documento tem valor mas a categoria ainda não tem lançamento no
    Razão, a categoria aparece mesmo assim (contabilizado=0) - é exatamente a
    "despesa já documentada mas ainda não contabilizada". Nunca inventa
    valor: sem documento extraído, valor_documentos fica 0."""

    def __init__(self, razao_repo: RazaoRepository, auditoria_repo: AuditoriaRepository):
        self._razao_repo = razao_repo
        self._auditoria_repo = auditoria_repo

    def executar(
        self, processo_codigo: str, mes_referencia: date, documentos: list[Documento] | None = None
    ) -> ResultadoComposicao:
        lancamentos = self._razao_repo.listar_por_processo(processo_codigo, mes_referencia)

        totais: dict[CategoriaLancamento, dict[str, Decimal]] = {}
        pendencias: list[str] = []

        def acumular(categoria: CategoriaLancamento, debito: Decimal, credito: Decimal, rateado: bool) -> None:
            bucket = totais.setdefault(
                categoria, {"debito": Decimal("0"), "credito": Decimal("0"), "rateado": Decimal("0")}
            )
            bucket["debito"] += debito
            bucket["credito"] += credito
            if rateado:
                bucket["rateado"] += debito + credito

        for lancamento in lancamentos:
            bases = {processo_base(c) for c in lancamento.processos_codigos}
            categoria = lancamento.categoria_classificada or CategoriaLancamento.OUTRAS_DESPESAS

            if len(bases) <= 1:
                acumular(categoria, lancamento.valor_debito, lancamento.valor_credito, rateado=False)
                continue

            if not lancamento.rateio_aplicado:
                pendencias.append(
                    f'Lançamento "{lancamento.historico}" cita múltiplos processos '
                    f"({', '.join(sorted(bases))}) mas o rateio ainda não foi aplicado (Fase 4) - "
                    "valor não incluído na composição."
                )
                continue

            memoria = self._auditoria_repo.buscar("rateio_lancamento", lancamento.id)
            participante = (
                next((p for p in memoria.get("participantes", []) if p["processo"] == processo_codigo), None)
                if memoria
                else None
            )
            if participante is None:
                pendencias.append(
                    f'Lançamento "{lancamento.historico}" foi marcado como rateado mas não há memória de '
                    f"cálculo para o processo {processo_codigo} - valor não incluído na composição."
                )
                continue

            acumular(
                categoria,
                Decimal(participante["valor_debito_destinado"]),
                Decimal(participante["valor_credito_destinado"]),
                rateado=True,
            )

        valores_documentos: dict[CategoriaLancamento, Decimal] = {}
        for documento in documentos or []:
            categoria_doc = categoria_do_documento(documento.tipo)
            if categoria_doc is None or documento.valor_extraido is None:
                continue
            valores_documentos[categoria_doc] = valores_documentos.get(categoria_doc, Decimal("0")) + documento.valor_extraido

        categorias_ordenadas = list(totais.keys())
        for categoria in valores_documentos:
            if categoria not in totais:
                categorias_ordenadas.append(categoria)

        itens: list[ItemComposicao] = []
        saldo_final = Decimal("0")
        zero = Decimal("0")
        for categoria in categorias_ordenadas:
            valores = totais.get(categoria, {"debito": zero, "credito": zero, "rateado": zero})
            net = valores["debito"] - valores["credito"]
            saldo_final += net
            valor_documentos = valores_documentos.get(categoria, zero)
            itens.append(
                ItemComposicao(
                    categoria=categoria,
                    valor_documentos=valor_documentos,
                    valor_contabilizado=net,
                    valor_rateado=valores["rateado"],
                    percentual_rateio=None,
                    diferenca=valor_documentos - net,
                )
            )

        composicao = ComposicaoContabil(processo_codigo=processo_codigo, mes_referencia=mes_referencia, itens=itens)
        return ResultadoComposicao(composicao=composicao, saldo_final=saldo_final, pendencias_rateio=pendencias)
