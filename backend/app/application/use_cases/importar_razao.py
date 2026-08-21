from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.domain.entities import CategoriaLancamento
from app.domain.ports import LancamentoClassifier, RazaoParser, RazaoRepository
from app.domain.processo_codigo import processo_base


@dataclass
class ResumoImportacaoRazao:
    mes_referencia: date | None = None
    total_lancamentos: int = 0
    total_valor_debito: Decimal = Decimal("0")
    total_valor_credito: Decimal = Decimal("0")
    processos_citados: list[str] = field(default_factory=list)
    lancamentos_sem_processo: int = 0
    lancamentos_multi_processo: int = 0
    por_categoria: dict[str, int] = field(default_factory=dict)


class ImportarRazaoUseCase:
    """Lê o Razão Contábil do mês, classifica cada lançamento por categoria e
    persiste - a aplicação do rateio multi-processo em si é a Fase 4
    (Matriz Mestre de Rateio); aqui só identificamos os candidatos."""

    def __init__(
        self,
        parser: RazaoParser,
        classifier: LancamentoClassifier,
        repo: RazaoRepository,
    ):
        self._parser = parser
        self._classifier = classifier
        self._repo = repo

    def executar(self, conteudo: bytes, nome_arquivo: str) -> ResumoImportacaoRazao:
        lancamentos = self._parser.parse(conteudo, nome_arquivo)

        resumo = ResumoImportacaoRazao()
        processos_vistos: set[str] = set()

        for lancamento in lancamentos:
            categoria = self._classifier.classificar(lancamento.historico, lancamento.conta_contabil)
            lancamento.categoria_classificada = CategoriaLancamento(categoria)

            resumo.total_lancamentos += 1
            resumo.total_valor_debito += lancamento.valor_debito
            resumo.total_valor_credito += lancamento.valor_credito
            resumo.por_categoria[categoria] = resumo.por_categoria.get(categoria, 0) + 1

            bases = {processo_base(c) for c in lancamento.processos_codigos}
            if not bases:
                resumo.lancamentos_sem_processo += 1
            elif len(bases) >= 2:
                resumo.lancamentos_multi_processo += 1
            processos_vistos.update(bases)

        if lancamentos:
            resumo.mes_referencia = lancamentos[0].mes_referencia
        resumo.processos_citados = sorted(processos_vistos)

        self._repo.salvar_lote(lancamentos)
        return resumo
