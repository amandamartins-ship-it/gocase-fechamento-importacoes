"""Calibrado contra 3 documentos REAIS abertos em 2026-07-26 (pasta
"WMF - FATURAMENTO FINAL" de GOC25129.1): um DAI da Infraero (Armazenagem),
uma NFS-e municipal (Honorários) e a fatura própria da trading (Frete
Internacional) - cada um seguido do comprovante de pagamento bancário. Os
textos abaixo reproduzem os trechos relevantes reais (extraídos via
pdfplumber), não são inventados."""

from decimal import Decimal

from app.infrastructure.extractors.valor_documento import extrair_valor_do_texto, extrair_valor_documento

TEXTO_ARMAZENAGEM_DAI = """
DAI - DOCUMENTO DE ARRECADAÇÃO DE IMPORTAÇÃO
15.578.569/0001-06 - CONCESSIONÁRIA AER INT. GUARULHOS SA
DATA/HORA DE RECEBIMENTO VALOR DA CARGA QT. VOLUME PESO
05.02.2026 20:56:21 41.932,50 12,000 271,000
VALOR A PAGAR
Período Tabela 7 Tabela 8 Tabela Valor Pago Retenção Valor a Pagar Data Vencimento
3 691,89 21,50 0,00 0,00 0,00 713,39 14.02.2026
-----------------------------------------------------------------------------------------------------------------------------
CONSIGNATÁRIO
Valor a pagar 713,39
-----------------------------------------------------------------------------------------------------------------------------
SISBB - SISTEMA DE INFORMACOES BANCO DO BRASIL
COMPROVANTE DE PAGAMENTO
Valor em Dinheiro 713,39
Valor em Cheque 0,00
Valor Total 713,39
"""

TEXTO_HONORARIOS_NFSE = """
NOTA FISCAL ELETRÔNICA DE SERVIÇO - NFS-e
Valor do Serviço
R$ 750,00
VALOR TOTAL DA NFS-e
Valor do Serviço R$ 750,00
Valor Líquido da NFS-e R$ 750,00
-----------------------------------------------------------------------------------------------------------------------------
comprovante de transferência
dados da transação
valor R$ 750,00
data da transferência 24/02/2026
"""

TEXTO_FRETE_FATURA_WMF = """
FATURA 01922-0226
Descrição Moeda Valor na Moeda Taxa Valor em Reais
Frete Internacional USD 1.755,00 5,57430 9.782,90
Taxas de origem USD 350,00 5,57430 1.951,01
Total: 12.291,35
-----------------------------------------------------------------------------------------------------------------------------
RECIBO 01922-0226
Total: 12.291,35
Valor por extenso: DOZE MIL E DUZENTOS E NOVENTA E UM REAIS E TRINTA E CINCO CENTAVOS
"""


def test_extrai_valor_da_armazenagem_dai():
    assert extrair_valor_do_texto(TEXTO_ARMAZENAGEM_DAI) == Decimal("713.39")


def test_extrai_valor_dos_honorarios_nfse():
    assert extrair_valor_do_texto(TEXTO_HONORARIOS_NFSE) == Decimal("750.00")


def test_extrai_valor_do_frete_fatura_wmf():
    assert extrair_valor_do_texto(TEXTO_FRETE_FATURA_WMF) == Decimal("12291.35")


def test_texto_sem_nenhum_marcador_retorna_none():
    assert extrair_valor_do_texto("PROPOSTA COMERCIAL sem nenhum valor reconhecível aqui") is None


def test_texto_vazio_retorna_none():
    assert extrair_valor_do_texto("") is None


def test_mime_type_nao_pdf_retorna_none_sem_tentar_ler():
    conteudo_qualquer = b"nao importa o conteudo"
    assert extrair_valor_documento(conteudo_qualquer, "application/vnd.ms-excel") is None
    assert extrair_valor_documento(conteudo_qualquer, None) is None


def test_pdf_corrompido_ou_sem_texto_retorna_none_nao_lanca_excecao():
    assert extrair_valor_documento(b"isto nao e um pdf de verdade", "application/pdf") is None
