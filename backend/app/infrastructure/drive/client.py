"""Descoberta de processos/embarques/documentos na pasta Importações do Drive.

Não depende de nomes fixos de arquivo (regex sobre padrões, não paths exatos),
mas foi calibrado contra a estrutura real vista em 2026/GO COMERCIO|BB
INDUSTRIA/<processo>/<embarque>/... (ver app/domain/entities.py e o plano da
Fase 2). Pastas "OLD" (versões substituídas de documentos) são sempre
ignoradas, em qualquer profundidade.
"""

import io
import re

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.domain.entities import Documento, DocumentoRef, Embarque, Processo, StatusLeituraDocumento
from app.domain.ports import DocumentClassifier
from app.infrastructure.classification.keyword_classifier import pasta_deve_ser_ignorada
from app.infrastructure.drive.oauth import load_credentials

FOLDER_MIME = "application/vnd.google-apps.folder"

PROCESSO_REGEX = re.compile(r"^((?:BBI|GOC)\d{5})\b(.*)$")
EMBARQUE_REGEX = re.compile(r"^((?:BBI|GOC)\d{5}\.\d+)\b(.*)$")


class DriveAuthError(RuntimeError):
    """Levantado quando não há um token OAuth válido - o usuário precisa logar em /drive/oauth/login."""


class GoogleDriveRepository:
    def __init__(self, classifier: DocumentClassifier):
        self._classifier = classifier
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service
        creds = load_credentials()
        if creds is None or not creds.valid:
            raise DriveAuthError("Sem token Google válido - faça login em /drive/oauth/login")
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _listar_filhos(self, folder_id: str) -> list[dict]:
        service = self._get_service()
        filhos: list[dict] = []
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            filhos.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return filhos

    def encontrar_arquivo_por_nome(self, nome: str) -> str | None:
        """Busca um arquivo (não pasta) pelo nome exato em qualquer lugar do Drive
        visível à conta autenticada - usado para achar Controle de Importações.xlsx."""
        service = self._get_service()
        nome_escapado = nome.replace("'", "\\'")
        resp = (
            service.files()
            .list(
                q=f"name = '{nome_escapado}' and trashed = false",
                fields="files(id, name)",
                pageSize=5,
            )
            .execute()
        )
        arquivos = resp.get("files", [])
        return arquivos[0]["id"] if arquivos else None

    def baixar_conteudo(self, drive_file_id: str) -> bytes:
        service = self._get_service()
        request = service.files().get_media(fileId=drive_file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        concluido = False
        while not concluido:
            _, concluido = downloader.next_chunk()
        return buffer.getvalue()

    def _encontrar_pasta_importacoes(self) -> str:
        service = self._get_service()
        settings_nome = "Importações"
        resp = (
            service.files()
            .list(
                q=(
                    f"name = '{settings_nome}' and mimeType = '{FOLDER_MIME}' and trashed = false"
                ),
                fields="files(id, name)",
                pageSize=10,
            )
            .execute()
        )
        arquivos = resp.get("files", [])
        if not arquivos:
            raise DriveAuthError(
                f"Pasta '{settings_nome}' não encontrada no Drive da conta autenticada - "
                "confirme que a conta logada tem acesso a ela."
            )
        return arquivos[0]["id"]

    def _coletar_documentos(self, pasta_id: str, caminho: str) -> list[tuple[DocumentoRef, str]]:
        """Percorre recursivamente uma pasta (embarque, ou pasta solta dentro do processo),
        pulando qualquer subpasta "OLD" em qualquer profundidade. Retorna (ref, tipo)."""
        documentos: list[tuple[DocumentoRef, str]] = []
        for item in self._listar_filhos(pasta_id):
            nome = item["name"]
            if item["mimeType"] == FOLDER_MIME:
                if pasta_deve_ser_ignorada(nome):
                    continue
                documentos.extend(self._coletar_documentos(item["id"], f"{caminho}/{nome}"))
            else:
                ref = DocumentoRef(
                    drive_file_id=item["id"],
                    nome_arquivo=nome,
                    caminho=f"{caminho}/{nome}",
                    mime_type=item["mimeType"],
                )
                tipo = self._classifier.classificar(ref)
                documentos.append((ref, tipo))
        return documentos

    def _montar_embarque(self, codigo: str, pasta_id: str, caminho: str) -> Embarque:
        embarque = Embarque(codigo=codigo, drive_folder_id=pasta_id)
        for ref, tipo in self._coletar_documentos(pasta_id, caminho):
            embarque.documentos.append(
                Documento(ref=ref, tipo=tipo, status_leitura=StatusLeituraDocumento.PENDENTE)
            )
        return embarque

    def _montar_processo(self, empresa_codigo: str, codigo: str, descricao: str, pasta_id: str, caminho: str, ano: int | None) -> Processo:
        processo = Processo(
            codigo=codigo,
            empresa_codigo=empresa_codigo,
            descricao=descricao or None,
            fornecedor=descricao.split(" - ")[-1].strip() if " - " in descricao else None,
            ano=ano,
            drive_folder_id=pasta_id,
        )

        filhos = self._listar_filhos(pasta_id)
        subpastas_embarque = []
        soltos_pasta_ids = []  # subpastas que não são embarque nem OLD - tratadas como "soltas"
        for item in filhos:
            if item["mimeType"] != FOLDER_MIME:
                continue
            if pasta_deve_ser_ignorada(item["name"]):
                continue
            match = EMBARQUE_REGEX.match(item["name"])
            if match:
                subpastas_embarque.append((match.group(1), item["id"], item["name"]))
            else:
                soltos_pasta_ids.append((item["id"], item["name"]))

        for embarque_codigo, embarque_pasta_id, nome_pasta in subpastas_embarque:
            embarque = self._montar_embarque(embarque_codigo, embarque_pasta_id, f"{caminho}/{nome_pasta}")
            partes = nome_pasta.split(" - ", 1)
            if len(partes) > 1:
                embarque.referencia_trading = partes[1].strip()
            processo.embarques.append(embarque)

        # Documentos soltos direto na pasta do processo (ex processos de "Serviço", sem
        # sub-pasta de embarque) + subpastas que não bateram nem com OLD nem com o padrão
        # de embarque: viram um embarque implícito == o próprio código do processo, para
        # nunca perder um documento real por falta de sub-pasta dedicada.
        embarque_implicito = Embarque(codigo=codigo, drive_folder_id=pasta_id)
        for item in filhos:
            if item["mimeType"] == FOLDER_MIME:
                continue
            ref = DocumentoRef(
                drive_file_id=item["id"],
                nome_arquivo=item["name"],
                caminho=f"{caminho}/{item['name']}",
                mime_type=item["mimeType"],
            )
            tipo = self._classifier.classificar(ref)
            embarque_implicito.documentos.append(
                Documento(ref=ref, tipo=tipo, status_leitura=StatusLeituraDocumento.PENDENTE)
            )
        for pasta_solta_id, nome_pasta in soltos_pasta_ids:
            for ref, tipo in self._coletar_documentos(pasta_solta_id, f"{caminho}/{nome_pasta}"):
                embarque_implicito.documentos.append(
                    Documento(ref=ref, tipo=tipo, status_leitura=StatusLeituraDocumento.PENDENTE)
                )
        if embarque_implicito.documentos:
            processo.embarques.append(embarque_implicito)

        return processo

    def listar_processos(self) -> list[Processo]:
        importacoes_id = self._encontrar_pasta_importacoes()
        processos: list[Processo] = []

        for ano_item in self._listar_filhos(importacoes_id):
            if ano_item["mimeType"] != FOLDER_MIME or not re.fullmatch(r"\d{4}", ano_item["name"]):
                continue
            ano = int(ano_item["name"])
            for empresa_item in self._listar_filhos(ano_item["id"]):
                if empresa_item["mimeType"] != FOLDER_MIME:
                    continue
                for processo_item in self._listar_filhos(empresa_item["id"]):
                    if processo_item["mimeType"] != FOLDER_MIME:
                        continue
                    if pasta_deve_ser_ignorada(processo_item["name"]):
                        continue
                    match = PROCESSO_REGEX.match(processo_item["name"])
                    if not match:
                        continue  # pasta que não é um processo de importação (ex "FIRST - IMP-02 12737")
                    codigo, resto = match.groups()
                    descricao = resto.lstrip(" -").strip()
                    empresa_codigo = codigo[:3]
                    caminho = f"Importações/{ano_item['name']}/{empresa_item['name']}/{processo_item['name']}"
                    processos.append(
                        self._montar_processo(
                            empresa_codigo, codigo, descricao, processo_item["id"], caminho, ano
                        )
                    )
        return processos
