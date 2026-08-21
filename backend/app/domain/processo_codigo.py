import re

_SUFIXO_EMBARQUE = re.compile(r"\.\d+$")


def processo_base(codigo: str) -> str:
    """GOC25129.1 -> GOC25129 - para comparar se 2 códigos citados juntos são,
    na prática, o mesmo processo (não um caso de rateio entre processos)."""
    return _SUFIXO_EMBARQUE.sub("", codigo)
