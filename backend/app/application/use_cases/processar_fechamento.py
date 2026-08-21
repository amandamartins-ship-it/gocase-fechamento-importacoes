from dataclasses import dataclass
from datetime import date

from app.application.use_cases.montar_composicao import MontarComposicaoUseCase
from app.application.use_cases.validar_fechamento import ValidarFechamentoUseCase
from app.domain.entities import ComposicaoContabil, Processo, ResultadoFechamento
from app.domain.indicadores import IndicadoresDashboard, calcular_indicadores
from app.domain.ports import ComposicaoRepository, FechamentoRepository, ProcessoRepository, RazaoRepository


@dataclass
class ResultadoProcessamentoProcesso:
    fechamento: ResultadoFechamento
    composicao: ComposicaoContabil


class ProcessarFechamentoProcessoUseCase:
    def __init__(
        self,
        processo_repo: ProcessoRepository,
        montar_composicao: MontarComposicaoUseCase,
        validar_fechamento: ValidarFechamentoUseCase,
        composicao_repo: ComposicaoRepository,
        fechamento_repo: FechamentoRepository,
    ):
        self._processo_repo = processo_repo
        self._montar_composicao = montar_composicao
        self._validar_fechamento = validar_fechamento
        self._composicao_repo = composicao_repo
        self._fechamento_repo = fechamento_repo

    def executar(self, processo_codigo: str, mes_referencia: date) -> ResultadoProcessamentoProcesso:
        processo = self._processo_repo.buscar_por_codigo(processo_codigo)
        if processo is None:
            # citado no Razão mas nunca descoberto no Drive (Fase 2 não rodou pra ele ainda) -
            # segue sem documentos conhecidos, o que corretamente resulta em Bloqueado.
            processo = Processo(codigo=processo_codigo, empresa_codigo=processo_codigo[:3])

        documentos = [doc for embarque in processo.embarques for doc in embarque.documentos]
        resultado_composicao = self._montar_composicao.executar(processo_codigo, mes_referencia, documentos)
        resultado_fechamento = self._validar_fechamento.executar(processo, resultado_composicao, mes_referencia)

        self._composicao_repo.salvar(resultado_composicao.composicao)
        self._fechamento_repo.salvar(resultado_fechamento)

        return ResultadoProcessamentoProcesso(
            fechamento=resultado_fechamento, composicao=resultado_composicao.composicao
        )


@dataclass
class ResumoProcessamentoFechamento:
    indicadores: IndicadoresDashboard
    resultados: list[ResultadoFechamento]


class ProcessarFechamentoMesUseCase:
    """Roda o fechamento de todos os processos relevantes do mês: os já
    descobertos no Drive (Fase 2) mais os citados em algum lançamento do
    Razão daquele mês (mesmo que ainda não sincronizados) - união dos dois,
    para nunca deixar um processo silenciosamente de fora."""

    def __init__(
        self,
        processo_repo: ProcessoRepository,
        razao_repo: RazaoRepository,
        processar_processo: ProcessarFechamentoProcessoUseCase,
    ):
        self._processo_repo = processo_repo
        self._razao_repo = razao_repo
        self._processar_processo = processar_processo

    def executar(self, mes_referencia: date) -> ResumoProcessamentoFechamento:
        codigos_no_razao = set(self._razao_repo.listar_processos_citados(mes_referencia))
        codigos_sincronizados = {p.codigo for p in self._processo_repo.listar()}
        todos_codigos = sorted(codigos_no_razao | codigos_sincronizados)

        resultados_com_composicao = [
            self._processar_processo.executar(codigo, mes_referencia) for codigo in todos_codigos
        ]

        indicadores = calcular_indicadores(
            [(r.fechamento, r.composicao.itens) for r in resultados_com_composicao]
        )
        return ResumoProcessamentoFechamento(
            indicadores=indicadores,
            resultados=[r.fechamento for r in resultados_com_composicao],
        )
