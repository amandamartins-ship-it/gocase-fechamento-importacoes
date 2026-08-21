"""Ports (interfaces) que a camada de aplicação depende e a infraestrutura implementa.

Mantém os casos de uso testáveis sem Drive/Postgres reais (ver app/tests).
"""

from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.entities import (
    ComposicaoContabil,
    Documento,
    DocumentoRef,
    LancamentoRazao,
    MatrizRateio,
    Processo,
    ResultadoFechamento,
    StatusLeituraDocumento,
)


class DriveRepository(Protocol):
    """Acesso de leitura ao Google Drive (pasta Importações)."""

    def listar_processos(self) -> list[Processo]:
        """Descobre todos os processos/embarques e seus documentos na pasta Importações."""
        ...

    def baixar_conteudo(self, drive_file_id: str) -> bytes:
        """Baixa os bytes de um arquivo do Drive para extração local."""
        ...


class DocumentClassifier(Protocol):
    def classificar(self, ref: DocumentoRef) -> str:
        """Retorna o TipoDocumento (como string) para um arquivo, por nome/caminho."""
        ...


class DocumentExtractor(Protocol):
    def suporta(self, ref: DocumentoRef) -> bool: ...

    def extrair(self, ref: DocumentoRef, conteudo: bytes) -> Documento:
        """Extrai texto/valor de um documento; nunca lança para formato não suportado."""
        ...


class RazaoParser(Protocol):
    def parse(self, conteudo: bytes, nome_arquivo: str) -> list[LancamentoRazao]: ...


class LancamentoClassifier(Protocol):
    def classificar(self, historico: str, conta_contabil: str | None) -> str:
        """Retorna a CategoriaLancamento (como string), considerando regras aprendidas."""
        ...


class RateioMatrizBuilder(Protocol):
    def nfs_do_processo(self, processo_codigo: str) -> set[str]:
        """NFs em que este processo aparece no Controle de Importações (Controle PIs)."""
        ...

    def construir(self, processos_codigos: list[str], nf_referencia: str) -> MatrizRateio | None:
        """Constrói a Matriz Mestre de Rateio de uma NF entre exatamente os processos informados
        (normalmente os processos citados juntos num mesmo lançamento do Razão) - retorna None se
        faltar quantidade real para algum deles, nunca inventa um percentual."""
        ...


class ProcessoRepository(Protocol):
    def salvar(self, processo: Processo) -> Processo: ...

    def buscar_por_codigo(self, codigo: str) -> Processo | None: ...

    def listar(self) -> list[Processo]: ...

    def atualizar_valor_documento(
        self, documento_id: int, valor_extraido: Decimal | None, status_leitura: StatusLeituraDocumento
    ) -> None:
        """Persiste o resultado da extração de valor (Fase 9) para um documento já
        existente, sem tocar no restante do processo/embarque."""
        ...


class RazaoRepository(Protocol):
    def salvar_lote(self, lancamentos: list[LancamentoRazao]) -> None: ...

    def listar_por_processo(self, processo_codigo: str, mes_referencia: date) -> list[LancamentoRazao]: ...

    def listar_multi_processo_pendentes(self, mes_referencia: date) -> list[LancamentoRazao]:
        """Lançamentos do mês que citam 2+ processos e ainda não tiveram o rateio aplicado."""
        ...

    def marcar_rateio_aplicado(self, lancamento_id: int) -> None: ...

    def listar_processos_citados(self, mes_referencia: date) -> list[str]:
        """Códigos-base de todo processo citado em algum lançamento do mês."""
        ...

    def listar_todos(self, mes_referencia: date) -> list[LancamentoRazao]:
        """Todos os lançamentos do mês, independente de processo."""
        ...


class AuditoriaRepository(Protocol):
    def registrar(self, referencia_tipo: str, referencia_id: int, memoria: dict) -> None: ...

    def buscar(self, referencia_tipo: str, referencia_id: int) -> dict | None: ...


class RateioMatrizRepository(Protocol):
    def salvar_participante(
        self, processo_codigo: str, nf_referencia: str, qtd_itens_processo: int, qtd_itens_total_nf: int,
        percentual: object, fonte: str | None,
    ) -> None: ...


class ComposicaoRepository(Protocol):
    def salvar(self, composicao: ComposicaoContabil) -> None:
        """Substitui a composição anterior do processo/mês pela recém-calculada."""
        ...


class FechamentoRepository(Protocol):
    def salvar(self, resultado: ResultadoFechamento) -> None: ...

    def buscar(self, processo_codigo: str, mes_referencia: date) -> ResultadoFechamento | None: ...

    def listar_por_mes(self, mes_referencia: date) -> list[ResultadoFechamento]: ...


class RegrasAprendidasRepository(Protocol):
    """Motor de aprendizado: toda correção do usuário (classificação de
    lançamento, tipo de documento, etc.) vira uma regra reutilizada nas
    próximas análises - nunca é aplicada retroativamente aos dados já
    processados, só dali em diante (próximo upload/sincronização)."""

    def registrar(
        self, tipo: str, padrao: str, valor_corrigido: str, justificativa: str | None, criado_por: str | None
    ) -> None: ...

    def buscar_valor_corrigido(self, tipo: str, texto: str) -> str | None:
        """Retorna o valor corrigido mais recente cuja 'padrao' aparece em texto
        (case-insensitive), ou None se nenhuma regra aprendida se aplica."""
        ...

    def listar(self, tipo: str | None = None) -> list[dict]: ...
