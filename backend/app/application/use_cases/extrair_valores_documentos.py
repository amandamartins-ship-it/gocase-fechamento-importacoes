from dataclasses import dataclass

from app.domain.documento_categoria import categoria_do_documento
from app.domain.entities import StatusLeituraDocumento
from app.domain.ports import DriveRepository, ProcessoRepository
from app.infrastructure.extractors.valor_documento import extrair_valor_documento


@dataclass
class ResultadoExtracaoValores:
    documentos_processados: int
    documentos_com_valor_encontrado: int


class ExtrairValoresDocumentosUseCase:
    """Baixa e lê o conteúdo real de cada documento da pasta FATURAMENTO FINAL
    ainda não processado (status PENDENTE) de um processo, extraindo o valor
    pago (Fase 9). Cada documento aqui já pertence a UM processo/embarque por
    construção (está dentro da pasta "FATURAMENTO FINAL" daquele processo) -
    o valor extraído é usado como está, sem nenhum rateio adicional (rateio é
    conceito do Razão compartilhado entre processos, Fase 4, não deste
    documento). Nunca reprocessa um documento já lido (preserva correções
    manuais futuras e evita reler PDF a cada sincronização)."""

    def __init__(self, processo_repo: ProcessoRepository, drive_repo: DriveRepository):
        self._processo_repo = processo_repo
        self._drive_repo = drive_repo

    def executar(self, processo_codigo: str) -> ResultadoExtracaoValores:
        processo = self._processo_repo.buscar_por_codigo(processo_codigo)
        if processo is None:
            return ResultadoExtracaoValores(documentos_processados=0, documentos_com_valor_encontrado=0)

        processados = 0
        com_valor = 0
        for embarque in processo.embarques:
            for documento in embarque.documentos:
                if categoria_do_documento(documento.tipo) is None:
                    continue  # fora do escopo desta fatia (só FATURAMENTO FINAL por enquanto)
                if documento.status_leitura != StatusLeituraDocumento.PENDENTE:
                    continue  # já processado numa extração anterior

                conteudo = self._drive_repo.baixar_conteudo(documento.ref.drive_file_id)
                valor = extrair_valor_documento(conteudo, documento.ref.mime_type)
                processados += 1

                if valor is not None:
                    com_valor += 1
                    documento.valor_extraido = valor
                    documento.status_leitura = StatusLeituraDocumento.OK
                else:
                    documento.status_leitura = StatusLeituraDocumento.SEM_TEXTO

                self._processo_repo.atualizar_valor_documento(
                    documento.id, documento.valor_extraido, documento.status_leitura
                )

        return ResultadoExtracaoValores(documentos_processados=processados, documentos_com_valor_encontrado=com_valor)
