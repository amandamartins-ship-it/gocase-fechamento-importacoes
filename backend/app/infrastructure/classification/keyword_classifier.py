from app.domain.entities import DocumentoRef, TipoDocumento
from app.domain.ports import DocumentClassifier, RegrasAprendidasRepository
from app.infrastructure.classification.dictionaries import classificar_por_nome

PASTAS_IGNORADAS = {"old"}


def pasta_deve_ser_ignorada(nome_pasta: str) -> bool:
    """Pastas "OLD" guardam versões substituídas de documentos (visto em BBI25167) -
    nunca devem ser descobertas/classificadas."""
    return nome_pasta.strip().lower() in PASTAS_IGNORADAS


class KeywordDocumentClassifier:
    """Implementação determinística do port DocumentClassifier: heurística por
    nome/caminho de arquivo, sem ML. Auditável - cada classificação vem de uma
    regra explícita em dictionaries.py, nunca um "palpite"."""

    def classificar(self, ref: DocumentoRef) -> TipoDocumento:
        return classificar_por_nome(ref.nome_arquivo, ref.caminho)


class DocumentClassifierComAprendizado:
    """Decora um DocumentClassifier: correções do usuário (motor de
    aprendizado) têm prioridade sobre o dicionário estático."""

    def __init__(self, base: DocumentClassifier, regras_repo: RegrasAprendidasRepository):
        self._base = base
        self._regras_repo = regras_repo

    def classificar(self, ref: DocumentoRef) -> str:
        aprendido = self._regras_repo.buscar_valor_corrigido("documento", ref.nome_arquivo)
        if aprendido:
            return aprendido
        return str(self._base.classificar(ref))
