from dataclasses import dataclass, field
from datetime import date

from app.domain.ports import AuditoriaRepository, RateioMatrizBuilder, RateioMatrizRepository, RazaoRepository
from app.domain.processo_codigo import processo_base

REFERENCIA_TIPO_RATEIO_LANCAMENTO = "rateio_lancamento"


@dataclass
class ResumoAplicacaoRateio:
    total_lancamentos_multi_processo: int = 0
    aplicados: int = 0
    pendentes: int = 0
    motivos_pendencia: list[dict] = field(default_factory=list)


class AplicarRateioUseCase:
    """Aplica a Matriz Mestre de Rateio aos lançamentos do Razão que citam 2+
    processos, usando a Nota Fiscal em comum entre eles no Controle de
    Importações. Nunca força um rateio quando a NF não é encontrada, é
    ambígua (mais de uma NF em comum) ou falta quantidade real para algum
    processo - esses casos ficam registrados como pendência explícita, para
    revisão manual, em vez de uma divisão arbitrária."""

    def __init__(
        self,
        razao_repo: RazaoRepository,
        rateio_builder: RateioMatrizBuilder,
        rateio_repo: RateioMatrizRepository,
        auditoria_repo: AuditoriaRepository,
    ):
        self._razao_repo = razao_repo
        self._rateio_builder = rateio_builder
        self._rateio_repo = rateio_repo
        self._auditoria_repo = auditoria_repo

    def executar(self, mes_referencia: date) -> ResumoAplicacaoRateio:
        lancamentos = self._razao_repo.listar_multi_processo_pendentes(mes_referencia)
        resumo = ResumoAplicacaoRateio(total_lancamentos_multi_processo=len(lancamentos))

        for lancamento in lancamentos:
            bases = sorted({processo_base(c) for c in lancamento.processos_codigos})
            nf, motivo = self._encontrar_nf_comum(bases)
            if nf is None:
                resumo.pendentes += 1
                resumo.motivos_pendencia.append(
                    {"lancamento_id": lancamento.id, "historico": lancamento.historico, "motivo": motivo}
                )
                continue

            matriz = self._rateio_builder.construir(bases, nf)
            if matriz is None:
                resumo.pendentes += 1
                resumo.motivos_pendencia.append(
                    {
                        "lancamento_id": lancamento.id,
                        "historico": lancamento.historico,
                        "motivo": f"NF {nf} encontrada, mas sem quantidade de itens válida para todos os processos citados.",
                    }
                )
                continue

            memoria_participantes = []
            for participante in matriz.participantes:
                valor_debito = lancamento.valor_debito * participante.percentual
                valor_credito = lancamento.valor_credito * participante.percentual
                participante.valor_destinado = valor_debito + valor_credito

                self._rateio_repo.salvar_participante(
                    participante.processo_codigo,
                    nf,
                    participante.qtd_itens,
                    matriz.qtd_itens_total_nf,
                    participante.percentual,
                    matriz.fonte,
                )
                memoria_participantes.append(
                    {
                        "processo": participante.processo_codigo,
                        "quantidade_itens": participante.qtd_itens,
                        "percentual": str(participante.percentual),
                        "valor_debito_destinado": str(valor_debito),
                        "valor_credito_destinado": str(valor_credito),
                    }
                )

            self._auditoria_repo.registrar(
                referencia_tipo=REFERENCIA_TIPO_RATEIO_LANCAMENTO,
                referencia_id=lancamento.id,
                memoria={
                    "lancamento_id": lancamento.id,
                    "historico": lancamento.historico,
                    "valor_debito_original": str(lancamento.valor_debito),
                    "valor_credito_original": str(lancamento.valor_credito),
                    "nf_utilizada": nf,
                    "quantidade_total_itens_nf": matriz.qtd_itens_total_nf,
                    "fonte": matriz.fonte,
                    "formula": (
                        "percentual = quantidade_itens_do_processo / quantidade_total_itens_da_nf; "
                        "valor_destinado = (valor_debito + valor_credito) * percentual"
                    ),
                    "participantes": memoria_participantes,
                },
            )
            self._razao_repo.marcar_rateio_aplicado(lancamento.id)
            resumo.aplicados += 1

        return resumo

    def _encontrar_nf_comum(self, processos_bases: list[str]) -> tuple[str | None, str | None]:
        nfs_comuns: set[str] | None = None
        for processo in processos_bases:
            nfs_do_processo = set(self._rateio_builder.nfs_do_processo(processo))
            nfs_comuns = nfs_do_processo if nfs_comuns is None else nfs_comuns & nfs_do_processo

        if not nfs_comuns:
            return None, (
                "Nenhuma Nota Fiscal em comum encontrada entre os processos citados "
                f"({', '.join(processos_bases)}) no Controle de Importações."
            )
        if len(nfs_comuns) > 1:
            return None, (
                f"Mais de uma Nota Fiscal em comum encontrada ({', '.join(sorted(nfs_comuns))}) "
                "entre os processos citados - ambíguo, requer revisão manual."
            )
        return next(iter(nfs_comuns)), None
