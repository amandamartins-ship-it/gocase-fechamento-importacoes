from decimal import Decimal

from app.application.use_cases.extrair_valores_documentos import ExtrairValoresDocumentosUseCase
from app.domain.entities import (
    Documento,
    DocumentoRef,
    Embarque,
    Processo,
    StatusLeituraDocumento,
    TipoDocumento,
)


class ProcessoRepoFalso:
    def __init__(self, processo):
        self._processo = processo
        self.atualizacoes: list[tuple] = []

    def buscar_por_codigo(self, codigo):
        return self._processo if self._processo and self._processo.codigo == codigo else None

    def atualizar_valor_documento(self, documento_id, valor_extraido, status_leitura):
        self.atualizacoes.append((documento_id, valor_extraido, status_leitura))


class DriveRepoFalso:
    def __init__(self, conteudos_por_file_id: dict[str, bytes]):
        self._conteudos = conteudos_por_file_id

    def baixar_conteudo(self, drive_file_id: str) -> bytes:
        return self._conteudos[drive_file_id]


def _documento(drive_file_id, tipo, status=StatusLeituraDocumento.PENDENTE, doc_id=1):
    return Documento(
        id=doc_id,
        ref=DocumentoRef(drive_file_id=drive_file_id, nome_arquivo=f"{drive_file_id}.pdf", caminho="x", mime_type="application/pdf"),
        tipo=tipo,
        status_leitura=status,
    )


def _processo_com_documentos(documentos) -> Processo:
    processo = Processo(codigo="GOC25129", empresa_codigo="GOC")
    embarque = Embarque(codigo="GOC25129.1", drive_folder_id="folder-1")
    embarque.documentos.extend(documentos)
    processo.embarques.append(embarque)
    return processo


def test_extrai_e_persiste_valor_de_documento_pendente(monkeypatch):
    doc = _documento("file-1", TipoDocumento.ARMAZENAGEM, doc_id=10)
    processo_repo = ProcessoRepoFalso(_processo_com_documentos([doc]))
    drive_repo = DriveRepoFalso({"file-1": b"conteudo-pdf-fake"})

    monkeypatch.setattr(
        "app.application.use_cases.extrair_valores_documentos.extrair_valor_documento",
        lambda conteudo, mime: Decimal("713.39"),
    )

    use_case = ExtrairValoresDocumentosUseCase(processo_repo, drive_repo)
    resultado = use_case.executar("GOC25129")

    assert resultado.documentos_processados == 1
    assert resultado.documentos_com_valor_encontrado == 1
    assert processo_repo.atualizacoes == [(10, Decimal("713.39"), StatusLeituraDocumento.OK)]


def test_documento_sem_valor_reconhecido_vira_sem_texto(monkeypatch):
    doc = _documento("file-2", TipoDocumento.HONORARIOS, doc_id=11)
    processo_repo = ProcessoRepoFalso(_processo_com_documentos([doc]))
    drive_repo = DriveRepoFalso({"file-2": b"conteudo-sem-marcador"})

    monkeypatch.setattr(
        "app.application.use_cases.extrair_valores_documentos.extrair_valor_documento",
        lambda conteudo, mime: None,
    )

    use_case = ExtrairValoresDocumentosUseCase(processo_repo, drive_repo)
    resultado = use_case.executar("GOC25129")

    assert resultado.documentos_processados == 1
    assert resultado.documentos_com_valor_encontrado == 0
    assert processo_repo.atualizacoes == [(11, None, StatusLeituraDocumento.SEM_TEXTO)]


def test_documento_ja_processado_nao_e_reprocessado(monkeypatch):
    doc = _documento("file-3", TipoDocumento.NUMERARIO, status=StatusLeituraDocumento.OK, doc_id=12)
    processo_repo = ProcessoRepoFalso(_processo_com_documentos([doc]))
    drive_repo = DriveRepoFalso({})  # nem deveria ser chamado

    use_case = ExtrairValoresDocumentosUseCase(processo_repo, drive_repo)
    resultado = use_case.executar("GOC25129")

    assert resultado.documentos_processados == 0
    assert processo_repo.atualizacoes == []


def test_documento_fora_do_escopo_faturamento_final_e_ignorado(monkeypatch):
    doc = _documento("file-4", TipoDocumento.DI, doc_id=13)
    processo_repo = ProcessoRepoFalso(_processo_com_documentos([doc]))
    drive_repo = DriveRepoFalso({})

    use_case = ExtrairValoresDocumentosUseCase(processo_repo, drive_repo)
    resultado = use_case.executar("GOC25129")

    assert resultado.documentos_processados == 0
    assert processo_repo.atualizacoes == []


def test_processo_inexistente_retorna_resultado_zerado():
    processo_repo = ProcessoRepoFalso(None)
    drive_repo = DriveRepoFalso({})

    use_case = ExtrairValoresDocumentosUseCase(processo_repo, drive_repo)
    resultado = use_case.executar("GOC99999")

    assert resultado.documentos_processados == 0
    assert resultado.documentos_com_valor_encontrado == 0
