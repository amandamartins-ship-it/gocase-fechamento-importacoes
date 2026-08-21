from app.domain.documento_categoria import categoria_do_documento
from app.domain.entities import CategoriaLancamento, TipoDocumento


def test_frete_internacional_e_frete_entrega_mapeiam_para_frete():
    assert categoria_do_documento(TipoDocumento.FRETE_INTERNACIONAL) == CategoriaLancamento.FRETE
    assert categoria_do_documento(TipoDocumento.FRETE_ENTREGA) == CategoriaLancamento.FRETE


def test_armazenagem_honorarios_numerario_mapeiam_direto():
    assert categoria_do_documento(TipoDocumento.ARMAZENAGEM) == CategoriaLancamento.ARMAZENAGEM
    assert categoria_do_documento(TipoDocumento.HONORARIOS) == CategoriaLancamento.HONORARIOS
    assert categoria_do_documento(TipoDocumento.NUMERARIO) == CategoriaLancamento.NUMERARIO


def test_icms_mapeia_para_outras_despesas_mesmo_precedente_do_lancamento():
    assert categoria_do_documento(TipoDocumento.ICMS) == CategoriaLancamento.OUTRAS_DESPESAS


def test_prestacao_contas_e_devolucao_saldo_ficam_fora_do_rollup_de_despesas():
    assert categoria_do_documento(TipoDocumento.PRESTACAO_CONTAS) is None
    assert categoria_do_documento(TipoDocumento.DEVOLUCAO_SALDO) is None


def test_tipos_nao_faturamento_final_ficam_fora():
    assert categoria_do_documento(TipoDocumento.DI) is None
    assert categoria_do_documento(TipoDocumento.OUTRO) is None
