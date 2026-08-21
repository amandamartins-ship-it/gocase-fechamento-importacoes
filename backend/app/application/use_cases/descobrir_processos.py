from dataclasses import dataclass, field

from app.domain.entities import Processo
from app.domain.ports import DriveRepository, ProcessoRepository


@dataclass
class ResumoDescoberta:
    total_processos: int = 0
    total_embarques: int = 0
    total_documentos: int = 0
    documentos_por_tipo: dict[str, int] = field(default_factory=dict)
    processos: list[str] = field(default_factory=list)


class DescobrirProcessosUseCase:
    """Varre a pasta Importações do Drive e persiste processos/embarques/documentos.

    Idempotente: cada execução substitui os embarques/documentos anteriores de um
    processo pelos atualmente encontrados no Drive (ver SqlAlchemyProcessoRepository) -
    é sempre uma "foto" atual, não um acúmulo.
    """

    def __init__(self, drive_repository: DriveRepository, processo_repository: ProcessoRepository):
        self._drive = drive_repository
        self._repo = processo_repository

    def executar(self) -> ResumoDescoberta:
        processos: list[Processo] = self._drive.listar_processos()
        resumo = ResumoDescoberta()
        for processo in processos:
            salvo = self._repo.salvar(processo)
            resumo.total_processos += 1
            resumo.processos.append(salvo.codigo)
            for embarque in salvo.embarques:
                resumo.total_embarques += 1
                for doc in embarque.documentos:
                    resumo.total_documentos += 1
                    chave = str(doc.tipo)
                    resumo.documentos_por_tipo[chave] = resumo.documentos_por_tipo.get(chave, 0) + 1
        return resumo
