from datetime import date
from decimal import Decimal

from app.domain.entities import LancamentoRazao, LinhaRazaoRateada
from app.domain.ports import AuditoriaRepository, FechamentoRepository, RazaoRepository
from app.domain.processo_codigo import processo_base

STATUS_SEM_FECHAMENTO_PROCESSADO = "Sem fechamento processado"


class GerarLinhasRazaoRateadoUseCase:
    """Reproduz o que a equipe faz manualmente: para cada lançamento que cita
    2+ processos, "copia a linha" uma vez por processo participante, com o
    valor já dividido pelo rateio (Fase 4) - o mesmo padrão visto em
    'Importações em Andamento' → aba 'Base 2026'. Cada linha final também é
    marcada com o status de fechamento (Fechado/Pendente/Bloqueado) do seu
    processo, igual à coluna "Status" da planilha real.

    Lançamentos multi-processo cujo rateio ainda não foi aplicado não geram
    linha aqui (o valor por processo ainda não existe de verdade) - eles já
    aparecem como pendência explícita em MontarComposicaoUseCase.
    """

    def __init__(
        self,
        razao_repo: RazaoRepository,
        auditoria_repo: AuditoriaRepository,
        fechamento_repo: FechamentoRepository,
    ):
        self._razao_repo = razao_repo
        self._auditoria_repo = auditoria_repo
        self._fechamento_repo = fechamento_repo

    def executar(self, mes_referencia: date) -> list[LinhaRazaoRateada]:
        lancamentos = self._razao_repo.listar_todos(mes_referencia)

        linhas: list[LinhaRazaoRateada] = []
        for lancamento in lancamentos:
            linhas.extend(self._linhas_do_lancamento(lancamento))

        status_por_processo: dict[str, str] = {}
        for linha in linhas:
            if linha.processo_full not in status_por_processo:
                resultado = self._fechamento_repo.buscar(linha.processo_full, mes_referencia)
                status_por_processo[linha.processo_full] = (
                    str(resultado.status) if resultado else STATUS_SEM_FECHAMENTO_PROCESSADO
                )
        for linha in linhas:
            linha.status = status_por_processo[linha.processo_full]

        return linhas

    def _linhas_do_lancamento(self, lancamento: LancamentoRazao) -> list[LinhaRazaoRateada]:
        codigos_unicos: list[str] = []
        for codigo in lancamento.processos_codigos:
            if codigo not in codigos_unicos:
                codigos_unicos.append(codigo)
        if not codigos_unicos:
            return []

        bases = sorted({processo_base(c) for c in codigos_unicos})

        def codigo_representativo(base: str) -> str:
            candidatos = [c for c in codigos_unicos if processo_base(c) == base]
            return max(candidatos, key=len)  # prefere o mais específico (com sufixo de embarque)

        def montar_linha(processo: str, processo_full: str, debito, credito) -> LinhaRazaoRateada:
            return LinhaRazaoRateada(
                empresa=lancamento.empresa,
                data=lancamento.data,
                conta=lancamento.conta_contabil,
                numero_contabil=lancamento.numero_contabil,
                unidade=lancamento.unidade,
                historico=lancamento.historico,
                debito=debito,
                credito=credito,
                processo=processo,
                processo_full=processo_full,
                lancamento_id=lancamento.id,
            )

        if len(bases) == 1:
            base = bases[0]
            return [montar_linha(codigo_representativo(base), base, lancamento.valor_debito, lancamento.valor_credito)]

        if not lancamento.rateio_aplicado:
            return []

        memoria = self._auditoria_repo.buscar("rateio_lancamento", lancamento.id) if lancamento.id else None
        if not memoria:
            return []

        linhas = []
        for participante in memoria.get("participantes", []):
            base = participante["processo"]
            linhas.append(
                montar_linha(
                    codigo_representativo(base) if base in bases else base,
                    base,
                    Decimal(participante["valor_debito_destinado"]),
                    Decimal(participante["valor_credito_destinado"]),
                )
            )
        return linhas
