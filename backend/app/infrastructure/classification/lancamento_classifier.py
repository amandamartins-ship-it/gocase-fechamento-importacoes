from app.domain.ports import LancamentoClassifier, RegrasAprendidasRepository
from app.infrastructure.classification.lancamento_dictionaries import classificar_historico
from app.infrastructure.util.texto import normalizar_texto


class KeywordLancamentoClassifier:
    """Implementação determinística do port LancamentoClassifier - mesma filosofia
    do classificador de documentos: regra explícita e auditável, nunca um chute."""

    def classificar(self, historico: str, conta_contabil: str | None) -> str:
        return str(classificar_historico(normalizar_texto(historico)))


class LancamentoClassifierComAprendizado:
    """Decora um LancamentoClassifier: correções do usuário (motor de
    aprendizado) têm prioridade sobre o dicionário estático."""

    def __init__(self, base: LancamentoClassifier, regras_repo: RegrasAprendidasRepository):
        self._base = base
        self._regras_repo = regras_repo

    def classificar(self, historico: str, conta_contabil: str | None) -> str:
        aprendido = self._regras_repo.buscar_valor_corrigido("classificacao", historico)
        if aprendido:
            return aprendido
        return self._base.classificar(historico, conta_contabil)
