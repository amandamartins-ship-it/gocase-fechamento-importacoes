from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import entities
from app.infrastructure.db import models

EMPRESAS_CONHECIDAS = {
    "GOC": "GO COMERCIO",
    "BBI": "BB INDUSTRIA",
}


def get_or_create_processo_minimo(db: Session, processo_codigo: str) -> models.Processo:
    """Usado pelos repositórios de composição/fechamento: um processo pode ter
    lançamentos no Razão antes de ter sido descoberto no Drive (Fase 2) - nesse
    caso criamos um registro mínimo (sem documentos) para não perder o
    resultado do fechamento, que já é o sinal correto (Bloqueado, por faltarem
    todos os documentos) em vez de simplesmente não persistir nada."""
    empresa_codigo = processo_codigo[:3]
    empresa = db.scalar(select(models.Empresa).where(models.Empresa.codigo == empresa_codigo))
    if empresa is None:
        empresa = models.Empresa(codigo=empresa_codigo, nome=EMPRESAS_CONHECIDAS.get(empresa_codigo, empresa_codigo))
        db.add(empresa)
        db.flush()

    processo = db.scalar(
        select(models.Processo).where(
            models.Processo.empresa_id == empresa.id, models.Processo.codigo == processo_codigo
        )
    )
    if processo is None:
        processo = models.Processo(empresa_id=empresa.id, codigo=processo_codigo)
        db.add(processo)
        db.flush()
    return processo


class SqlAlchemyProcessoRepository:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_empresa(self, codigo: str) -> models.Empresa:
        empresa = self.db.scalar(select(models.Empresa).where(models.Empresa.codigo == codigo))
        if empresa is None:
            empresa = models.Empresa(codigo=codigo, nome=EMPRESAS_CONHECIDAS.get(codigo, codigo))
            self.db.add(empresa)
            self.db.flush()
        return empresa

    def salvar(self, processo: entities.Processo) -> entities.Processo:
        """Descoberta é re-derivável do Drive a cada sincronização, mas o
        upsert é por identidade (embarque por código, documento por
        drive_file_id) - nunca apaga e recria tudo. Isso preserva
        `valor_extraido`/`status_leitura` de documentos já processados pela
        extração de valores (Fase 9); só reclassifica tipo/nome/mime_type,
        que podem legitimamente mudar (ex: uma correção do motor de
        aprendizado)."""
        empresa = self._get_or_create_empresa(processo.empresa_codigo)
        row = self.db.scalar(
            select(models.Processo).where(
                models.Processo.empresa_id == empresa.id, models.Processo.codigo == processo.codigo
            )
        )
        if row is None:
            row = models.Processo(empresa_id=empresa.id, codigo=processo.codigo)
            self.db.add(row)
            self.db.flush()

        row.descricao = processo.descricao
        row.fornecedor = processo.fornecedor
        row.ano = processo.ano
        row.drive_folder_id = processo.drive_folder_id

        embarques_antigos_por_codigo = {e.codigo: e for e in row.embarques}
        codigos_atuais: set[str] = set()

        for embarque in processo.embarques:
            codigos_atuais.add(embarque.codigo)
            embarque_row = embarques_antigos_por_codigo.get(embarque.codigo)
            if embarque_row is None:
                embarque_row = models.Embarque(processo_id=row.id, codigo=embarque.codigo)
                self.db.add(embarque_row)
                self.db.flush()

            embarque_row.trading = embarque.trading
            embarque_row.referencia_trading = embarque.referencia_trading
            embarque_row.drive_folder_id = embarque.drive_folder_id

            documentos_antigos_por_file_id = {d.drive_file_id: d for d in embarque_row.documentos}
            file_ids_atuais: set[str] = set()

            for doc in embarque.documentos:
                file_ids_atuais.add(doc.ref.drive_file_id)
                doc_row = documentos_antigos_por_file_id.get(doc.ref.drive_file_id)
                novo = doc_row is None
                if novo:
                    doc_row = models.Documento(embarque_id=embarque_row.id, drive_file_id=doc.ref.drive_file_id)
                    self.db.add(doc_row)

                doc_row.tipo = str(doc.tipo)
                doc_row.nome_arquivo = doc.ref.nome_arquivo
                doc_row.mime_type = doc.ref.mime_type
                if novo:
                    doc_row.status_leitura = str(doc.status_leitura)

            for drive_file_id, doc_row in documentos_antigos_por_file_id.items():
                if drive_file_id not in file_ids_atuais:
                    self.db.delete(doc_row)

        for codigo, embarque_row in embarques_antigos_por_codigo.items():
            if codigo not in codigos_atuais:
                self.db.delete(embarque_row)

        self.db.commit()
        self.db.refresh(row)
        return self._to_domain(row)

    def buscar_por_codigo(self, codigo: str) -> entities.Processo | None:
        row = self.db.scalar(select(models.Processo).where(models.Processo.codigo == codigo))
        return self._to_domain(row) if row else None

    def listar(self) -> list[entities.Processo]:
        rows = self.db.scalars(select(models.Processo)).all()
        return [self._to_domain(row) for row in rows]

    def atualizar_valor_documento(
        self, documento_id: int, valor_extraido: Decimal | None, status_leitura: entities.StatusLeituraDocumento
    ) -> None:
        doc_row = self.db.get(models.Documento, documento_id)
        if doc_row is None:
            return
        doc_row.valor_extraido = valor_extraido
        doc_row.status_leitura = str(status_leitura)
        self.db.commit()

    @staticmethod
    def _to_domain(row: models.Processo) -> entities.Processo:
        processo = entities.Processo(
            id=row.id,
            codigo=row.codigo,
            empresa_codigo=row.empresa.codigo,
            descricao=row.descricao,
            fornecedor=row.fornecedor,
            ano=row.ano,
            drive_folder_id=row.drive_folder_id,
        )
        for embarque_row in row.embarques:
            embarque = entities.Embarque(
                id=embarque_row.id,
                codigo=embarque_row.codigo,
                drive_folder_id=embarque_row.drive_folder_id,
                trading=embarque_row.trading,
                referencia_trading=embarque_row.referencia_trading,
            )
            for doc_row in embarque_row.documentos:
                embarque.documentos.append(
                    entities.Documento(
                        id=doc_row.id,
                        ref=entities.DocumentoRef(
                            drive_file_id=doc_row.drive_file_id,
                            nome_arquivo=doc_row.nome_arquivo,
                            caminho="",
                            mime_type=doc_row.mime_type,
                        ),
                        tipo=entities.TipoDocumento(doc_row.tipo),
                        status_leitura=entities.StatusLeituraDocumento(doc_row.status_leitura),
                        valor_extraido=doc_row.valor_extraido,
                    )
                )
            processo.embarques.append(embarque)
        return processo
