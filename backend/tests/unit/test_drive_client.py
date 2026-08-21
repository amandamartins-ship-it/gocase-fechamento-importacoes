"""Testa a lógica de varredura do GoogleDriveRepository (regex de processo/
embarque, documentos soltos, pastas OLD ignoradas) contra uma árvore fake que
reproduz a estrutura real vista no Drive - sem chamar a API do Google."""

import re

from app.domain.entities import TipoDocumento
from app.infrastructure.classification.keyword_classifier import KeywordDocumentClassifier
from app.infrastructure.drive.client import FOLDER_MIME, GoogleDriveRepository

PDF = "application/pdf"


def _folder(id_, name):
    return {"id": id_, "name": name, "mimeType": FOLDER_MIME}


def _file(id_, name, mime=PDF):
    return {"id": id_, "name": name, "mimeType": mime}


class FakeExecutable:
    def __init__(self, files):
        self._files = files

    def execute(self):
        return {"files": self._files, "nextPageToken": None}


class FakeFilesResource:
    def __init__(self, tree, importacoes_id):
        self.tree = tree
        self.importacoes_id = importacoes_id

    def list(self, q, fields, pageSize, pageToken=None):  # noqa: N803 - assinatura espelha googleapiclient
        if "name = 'Importa" in q:
            return FakeExecutable([{"id": self.importacoes_id, "name": "Importações"}])
        match = re.search(r"'([\w-]+)' in parents", q)
        folder_id = match.group(1)
        return FakeExecutable(self.tree.get(folder_id, []))


class FakeDriveService:
    def __init__(self, tree, importacoes_id):
        self._resource = FakeFilesResource(tree, importacoes_id)

    def files(self):
        return self._resource


def _montar_arvore_real():
    """Reproduz GOC25129 (com FATURAMENTO FINAL numerado), GOC25191 (serviço,
    sem embarque) e BBI25167 (2 embarques + pasta OLD em 2 profundidades)."""
    tree = {
        "importacoes": [_folder("ano2026", "2026")],
        "ano2026": [_folder("go_comercio", "GO COMERCIO"), _folder("bb_industria", "BB INDUSTRIA")],
        "go_comercio": [
            _folder("goc25129", "GOC25129 - Bag Charm (Linha Charms) - Newcom"),
            _folder("goc25191", "GOC25191 - Serviço - Extrema (Instalação Software) - Print Factory"),
        ],
        "bb_industria": [_folder("bbi25167", "BBI25167 - Capas de Celular MagSafe (Case Bold) - Sanfeng")],
        # GOC25129: 1 embarque com FATURAMENTO FINAL numerado (WMF)
        "goc25129": [_folder("goc25129_1", "GOC25129.1 - WMFIA261430")],
        "goc25129_1": [
            _file("f1", "DI - 26 0223149-4.pdf"),
            _file("f2", "GOC25129.1 - PL.pdf"),
            _file("f3", "NF 5926073 PROCESSO GOC25129.1.pdf"),
            _folder("goc25129_1_fat", "WMF - FATURAMENTO FINAL ( GOC25129.1)"),
        ],
        "goc25129_1_fat": [
            _file("f4", "1 - FRETE INTERNACIONAL.pdf"),
            _file("f5", "5 - HONORÁRIOS.pdf"),
        ],
        # GOC25191: processo de serviço, documentos soltos direto na pasta do processo
        "goc25191": [
            _file("f6", "INV 01 - # L INV-000002.pdf"),
            _file("f7", "SWIFT (100%) - CC 592633753 - GOC25191 - Print Factory.pdf"),
        ],
        # BBI25167: 2 embarques + 1 pasta OLD direto no processo + docs soltos
        "bbi25167": [
            _folder("bbi25167_1", "BBI25167.1 - CAI26002364 (Aéreo)"),
            _folder("bbi25167_2", "BBI25167.2 - CMI26000728 (LCL)"),
            _folder("bbi25167_old", "OLD"),
            _file("f8", "PI - BBI25167 - SANFENG.pdf"),
        ],
        "bbi25167_old": [_file("f9", "BBI25167-PI-SANFENG.xlsx")],  # nunca deve aparecer
        "bbi25167_1": [
            _file("f10", "NF 10634 PROCESSO BBI25167.1.pdf"),
            _folder("bbi25167_1_old", "OLD"),
            _folder("bbi25167_1_fat", "CODELI - FATURAMENTO FINAL (BBI25167.1)"),
        ],
        "bbi25167_1_old": [_file("f11", "DRAFT HAWB - SA260509081.pdf")],  # nunca deve aparecer
        "bbi25167_1_fat": [
            _file("f12", "I-AER-0550-26-ND.pdf"),
            _file("f13", "DEV SALDO BB IND COM I-AER-0550-26 - 6687,86.pdf"),
        ],
        "bbi25167_2": [_file("f14", "PL - BBI25167.2 - SANFENG (LCL sea freight).pdf")],
    }
    return tree, "importacoes"


def test_descoberta_completa_reflete_estrutura_real(monkeypatch):
    tree, importacoes_id = _montar_arvore_real()
    repo = GoogleDriveRepository(KeywordDocumentClassifier())
    monkeypatch.setattr(repo, "_get_service", lambda: FakeDriveService(tree, importacoes_id))

    processos = repo.listar_processos()
    por_codigo = {p.codigo: p for p in processos}

    # GOC25191 é "Serviço - ..." mas ainda começa com GOC + 5 dígitos, então DEVE ser
    # descoberto igual aos demais - se isso falhar, o regex está rejeitando processos
    # de serviço por engano (ver test_processo_de_servico_sem_pasta_de_embarque... abaixo).
    assert set(por_codigo) == {"GOC25129", "GOC25191", "BBI25167"}


def test_processo_de_servico_sem_pasta_de_embarque_e_descoberto(monkeypatch):
    tree, importacoes_id = _montar_arvore_real()
    repo = GoogleDriveRepository(KeywordDocumentClassifier())
    monkeypatch.setattr(repo, "_get_service", lambda: FakeDriveService(tree, importacoes_id))

    processos = repo.listar_processos()
    goc25191 = next(p for p in processos if p.codigo == "GOC25191")

    assert len(goc25191.embarques) == 1  # embarque implícito
    embarque_implicito = goc25191.embarques[0]
    assert embarque_implicito.codigo == "GOC25191"
    nomes = {d.ref.nome_arquivo for d in embarque_implicito.documentos}
    assert nomes == {"INV 01 - # L INV-000002.pdf", "SWIFT (100%) - CC 592633753 - GOC25191 - Print Factory.pdf"}


def test_pastas_old_nunca_aparecem_em_nenhuma_profundidade(monkeypatch):
    tree, importacoes_id = _montar_arvore_real()
    repo = GoogleDriveRepository(KeywordDocumentClassifier())
    monkeypatch.setattr(repo, "_get_service", lambda: FakeDriveService(tree, importacoes_id))

    processos = repo.listar_processos()
    todos_nomes = {
        doc.ref.nome_arquivo
        for processo in processos
        for embarque in processo.embarques
        for doc in embarque.documentos
    }
    assert "BBI25167-PI-SANFENG.xlsx" not in todos_nomes  # estava em OLD direto no processo
    assert "DRAFT HAWB - SA260509081.pdf" not in todos_nomes  # estava em OLD dentro de um embarque


def test_multiplos_embarques_e_faturamento_final_classificados_corretamente(monkeypatch):
    tree, importacoes_id = _montar_arvore_real()
    repo = GoogleDriveRepository(KeywordDocumentClassifier())
    monkeypatch.setattr(repo, "_get_service", lambda: FakeDriveService(tree, importacoes_id))

    processos = repo.listar_processos()
    bbi = next(p for p in processos if p.codigo == "BBI25167")
    codigos_embarque = {e.codigo for e in bbi.embarques}
    # 2 embarques reais + 1 embarque implícito para o "PI" solto direto na pasta do processo
    assert codigos_embarque == {"BBI25167.1", "BBI25167.2", "BBI25167"}

    embarque_1 = next(e for e in bbi.embarques if e.codigo == "BBI25167.1")
    por_nome = {d.ref.nome_arquivo: d.tipo for d in embarque_1.documentos}
    assert por_nome["NF 10634 PROCESSO BBI25167.1.pdf"] == TipoDocumento.NOTA_FISCAL
    # dentro da pasta FATURAMENTO FINAL da CODELI, siglas ambíguas (ND/NF) viram OUTRO,
    # mas "DEV SALDO" é reconhecido mesmo sem o padrão numerado da WMF.
    assert por_nome["I-AER-0550-26-ND.pdf"] == TipoDocumento.OUTRO
    assert por_nome["DEV SALDO BB IND COM I-AER-0550-26 - 6687,86.pdf"] == TipoDocumento.DEVOLUCAO_SALDO


def test_goc25129_faturamento_final_wmf_numerado(monkeypatch):
    tree, importacoes_id = _montar_arvore_real()
    repo = GoogleDriveRepository(KeywordDocumentClassifier())
    monkeypatch.setattr(repo, "_get_service", lambda: FakeDriveService(tree, importacoes_id))

    processos = repo.listar_processos()
    goc = next(p for p in processos if p.codigo == "GOC25129")
    assert goc.empresa_codigo == "GOC"
    embarque = goc.embarques[0]
    assert embarque.codigo == "GOC25129.1"
    assert embarque.referencia_trading == "WMFIA261430"
    por_nome = {d.ref.nome_arquivo: d.tipo for d in embarque.documentos}
    assert por_nome["1 - FRETE INTERNACIONAL.pdf"] == TipoDocumento.FRETE_INTERNACIONAL
    assert por_nome["5 - HONORÁRIOS.pdf"] == TipoDocumento.HONORARIOS
    assert por_nome["DI - 26 0223149-4.pdf"] == TipoDocumento.DI
