const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "fechamento_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail ?? "Erro na requisição");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function baixarArquivo(path: string, nomeArquivoFallback: string): Promise<void> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, { headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail ?? "Falha ao gerar o arquivo");
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const combinacao = /filename="?([^"]+)"?/.exec(disposition);
  const nomeArquivo = combinacao ? combinacao[1] : nomeArquivoFallback;

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export interface HealthResponse {
  status: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DriveStatus {
  conectado: boolean;
}

export interface ResumoSincronizacao {
  total_processos: number;
  total_embarques: number;
  total_documentos: number;
  documentos_por_tipo: Record<string, number>;
  processos: string[];
}

export interface ResumoImportacaoRazao {
  mes_referencia: string | null;
  total_lancamentos: number;
  total_valor_debito: number;
  total_valor_credito: number;
  processos_citados: string[];
  lancamentos_sem_processo: number;
  lancamentos_multi_processo: number;
  por_categoria: Record<string, number>;
}

export interface DashboardIndicadores {
  total_processos: number;
  processos_fechados: number;
  processos_pendentes: number;
  processos_bloqueados: number;
  valor_total_contabilizado: number;
  valor_total_rateado: number;
  valor_pendente: number;
  total_variacao_cambial: number;
  percentual_automacao: number;
  indice_qualidade_fechamento: number;
}

export interface ResumoAplicacaoRateio {
  total_lancamentos_multi_processo: number;
  aplicados: number;
  pendentes: number;
  motivos_pendencia: { lancamento_id: number; historico: string; motivo: string }[];
}

export interface ItemComposicao {
  categoria: string;
  valor_documentos: number;
  valor_contabilizado: number;
  valor_rateado: number;
  percentual_rateio: number | null;
  diferenca: number;
}

export interface FechamentoProcesso {
  processo_codigo: string;
  mes_referencia: string;
  status: string;
  saldo_final: number;
  variacao_cambial: number | null;
  motivos_pendencia: string[];
  composicao: ItemComposicao[];
}

export interface ResumoProcessamentoFechamento extends DashboardIndicadores {
  resultados: FechamentoProcesso[];
}

export interface ExtracaoValores {
  documentos_processados: number;
  documentos_com_valor_encontrado: number;
}

export interface ProcessoResumo {
  codigo: string;
  empresa_codigo: string;
  descricao: string | null;
  fornecedor: string | null;
  status: string | null;
  saldo_final: number | null;
}

export interface LancamentoResumo {
  id: number | null;
  historico: string;
  categoria: string | null;
  valor_debito: number;
  valor_credito: number;
  processos_codigos: string[];
  rateio_aplicado: boolean;
}

export interface ParticipanteRateio {
  processo: string;
  quantidade_itens: number;
  percentual: string;
  valor_debito_destinado: string;
  valor_credito_destinado: string;
}

export interface MemoriaRateio {
  lancamento_id: number;
  historico: string;
  valor_debito_original: string;
  valor_credito_original: string;
  nf_utilizada: string;
  quantidade_total_itens_nf: number;
  fonte: string;
  formula: string;
  participantes: ParticipanteRateio[];
}

export interface LinhaRateada {
  lancamento_id: number | null;
  empresa: string | null;
  data: string | null;
  conta: string | null;
  numero_contabil: string | null;
  unidade: string | null;
  historico: string;
  debito: number;
  credito: number;
  movimentacao: number;
  processo: string;
  processo_full: string;
  processo_controle_importacao: string;
  status: string | null;
}

export interface LinhasRateadasProcesso {
  linhas: LinhaRateada[];
  total_debito: number;
  total_credito: number;
  saldo_processo: number;
}

export interface RegraAprendida {
  id: number;
  tipo: string;
  padrao: string;
  valor_corrigido: string;
  justificativa: string | null;
  criado_por: string | null;
  criado_em: string;
}

export const CATEGORIAS_LANCAMENTO = [
  "Frete",
  "Armazenagem",
  "Honorários",
  "AFRMM",
  "Seguro",
  "Capatazia",
  "IOF",
  "Mercadoria",
  "Numerário",
  "Reembolso",
  "NF Entrada",
  "Variação Cambial",
  "Outras despesas",
];

export const TIPOS_DOCUMENTO = [
  "DI",
  "INVOICE_CI",
  "PACKING_LIST",
  "GLME",
  "AWB_HAWB",
  "NOTA_FISCAL",
  "XML_NFE",
  "NUMERARIO",
  "ICMS",
  "PROTOCOLO_DI",
  "RASCUNHO_NF_ENTRADA",
  "COMPROVANTE_IMPORTACAO",
  "RELATORIO_ITENS",
  "INSTRUCAO_DESEMBARACO",
  "FRETE_INTERNACIONAL",
  "FRETE_ENTREGA",
  "ARMAZENAGEM",
  "HONORARIOS",
  "PRESTACAO_CONTAS",
  "DEVOLUCAO_SALDO",
  "OUTRO",
];

export const api = {
  health: () => request<HealthResponse>("/health"),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  listarProcessos: (mesReferencia?: string) =>
    request<ProcessoResumo[]>(`/processos${mesReferencia ? `?mes_referencia=${mesReferencia}` : ""}`),
  listarLancamentos: (codigo: string, mesReferencia: string) =>
    request<LancamentoResumo[]>(`/processos/${codigo}/lancamentos?mes_referencia=${mesReferencia}`),
  linhasRateadas: (codigo: string, mesReferencia: string) =>
    request<LinhasRateadasProcesso>(`/processos/${codigo}/linhas-rateadas?mes_referencia=${mesReferencia}`),
  extrairValoresDocumentos: (codigo: string) =>
    request<ExtracaoValores>(`/processos/${codigo}/extrair-valores`, { method: "POST" }),
  obterFechamentoProcesso: (codigo: string, mesReferencia: string) =>
    request<FechamentoProcesso>(`/fechamento/${codigo}?mes_referencia=${mesReferencia}`),
  dashboard: () => request<DashboardIndicadores>("/processos/dashboard"),
  driveStatus: () => request<DriveStatus>("/drive/oauth/status"),
  driveLoginUrl: () => request<{ authorization_url: string }>("/drive/oauth/login"),
  driveSincronizar: () => request<ResumoSincronizacao>("/drive/sincronizar", { method: "POST" }),
  processarRazao: (arquivo: File) => {
    const formData = new FormData();
    formData.append("arquivo", arquivo);
    return request<ResumoImportacaoRazao>("/razao/upload", { method: "POST", body: formData });
  },
  aplicarRateio: (mesReferencia: string) =>
    request<ResumoAplicacaoRateio>(`/rateio/aplicar?mes_referencia=${mesReferencia}`, { method: "POST" }),
  processarFechamento: (mesReferencia: string) =>
    request<ResumoProcessamentoFechamento>(`/fechamento/processar?mes_referencia=${mesReferencia}`, {
      method: "POST",
    }),
  auditoriaRateio: (lancamentoId: number) =>
    request<{ memoria: MemoriaRateio }>(`/rateio/auditoria/${lancamentoId}`),
  corrigir: (payload: { tipo: string; padrao: string; valor_corrigido: string; justificativa?: string }) =>
    request<{ mensagem: string }>("/aprendizado/corrigir", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listarRegras: (tipo?: string) =>
    request<RegraAprendida[]>(`/aprendizado/regras${tipo ? `?tipo=${tipo}` : ""}`),
  baixarRazaoAtualizado: (mesReferencia: string) =>
    baixarArquivo(
      `/fechamento/exportar/razao-atualizado.xlsx?mes_referencia=${mesReferencia}`,
      "Razao_Atualizado.xlsx"
    ),
  baixarProcessosFechados: (mesReferencia: string) =>
    baixarArquivo(
      `/fechamento/exportar/processos-fechados.xlsx?mes_referencia=${mesReferencia}`,
      "Processos_Fechados.xlsx"
    ),
};
