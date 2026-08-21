import { useEffect, useState } from "react";
import {
  api,
  clearToken,
  DashboardIndicadores,
  DriveStatus,
  ResumoImportacaoRazao,
  ResumoSincronizacao,
} from "../api/client";
import CorrectionPanel from "../components/CorrectionPanel";
import ProcessoTable from "../components/ProcessoTable";
import RazaoDashboard from "../components/RazaoDashboard";

function mesAtualPadrao(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function Home({ onLogout }: { onLogout: () => void }) {
  const [indicadores, setIndicadores] = useState<DashboardIndicadores | null>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erroRazao, setErroRazao] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);
  const [resumoRazao, setResumoRazao] = useState<ResumoImportacaoRazao | null>(null);
  const [avisoRateio, setAvisoRateio] = useState<string | null>(null);
  const [mes, setMes] = useState<string>(mesAtualPadrao);
  const [driveStatus, setDriveStatus] = useState<DriveStatus | null>(null);
  const [sincronizando, setSincronizando] = useState(false);
  const [resumo, setResumo] = useState<ResumoSincronizacao | null>(null);
  const [erroDrive, setErroDrive] = useState<string | null>(null);

  function carregarDriveStatus() {
    api
      .driveStatus()
      .then(setDriveStatus)
      .catch(() => setDriveStatus(null));
  }

  useEffect(() => {
    api
      .dashboard()
      .then(setIndicadores)
      .catch(() => setIndicadores(null));
    carregarDriveStatus();
  }, []);

  async function handleConectarDrive() {
    try {
      const { authorization_url } = await api.driveLoginUrl();
      window.open(authorization_url, "_blank");
    } catch (err) {
      setErroDrive(err instanceof Error ? err.message : "Falha ao iniciar login do Drive");
    }
  }

  async function handleSincronizar() {
    setSincronizando(true);
    setErroDrive(null);
    setResumo(null);
    try {
      const resultado = await api.driveSincronizar();
      setResumo(resultado);
    } catch (err) {
      setErroDrive(err instanceof Error ? err.message : "Falha ao sincronizar com o Drive");
    } finally {
      setSincronizando(false);
    }
  }

  async function handleProcessar() {
    if (!arquivo) {
      setMensagem("Selecione o arquivo do Razão Contábil primeiro.");
      return;
    }
    setMensagem(null);
    setErroRazao(null);
    setResumoRazao(null);
    setAvisoRateio(null);
    setProcessando(true);
    try {
      const resultadoRazao = await api.processarRazao(arquivo);
      setResumoRazao(resultadoRazao);
      if (!resultadoRazao.mes_referencia) {
        return;
      }
      setMes(resultadoRazao.mes_referencia);

      try {
        await api.aplicarRateio(resultadoRazao.mes_referencia);
      } catch (err) {
        setAvisoRateio(
          `Rateio não pôde ser aplicado agora (${
            err instanceof Error ? err.message : "erro desconhecido"
          }) — o fechamento seguiu mesmo assim, com esses lançamentos marcados como pendência.`
        );
      }

      const resultadoFechamento = await api.processarFechamento(resultadoRazao.mes_referencia);
      setIndicadores(resultadoFechamento);
    } catch (err) {
      setErroRazao(err instanceof Error ? err.message : "Falha ao processar o Razão");
    } finally {
      setProcessando(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Fechamento Contábil de Importações</h1>
        <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
          <label className="muted-note" htmlFor="mes-referencia">
            Mês
          </label>
          <input
            id="mes-referencia"
            type="month"
            value={mes.slice(0, 7)}
            onChange={(e) => setMes(`${e.target.value}-01`)}
          />
          <button
            className="ghost"
            onClick={() => {
              clearToken();
              onLogout();
            }}
          >
            Sair
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Google Drive</h3>
        <div className="row" style={{ marginBottom: "0.9rem" }}>
          <span className="muted-note">Status:</span>
          {driveStatus?.conectado ? (
            <span className="pill good">Conectado</span>
          ) : (
            <span className="muted-note">Não conectado</span>
          )}
        </div>
        <div className="row">
          <button className="ghost" onClick={handleConectarDrive}>
            Conectar ao Google Drive
          </button>
          <button className="ghost" onClick={carregarDriveStatus}>
            Atualizar status
          </button>
          <button className="primary" onClick={handleSincronizar} disabled={sincronizando}>
            {sincronizando ? "Sincronizando..." : "Sincronizar documentos"}
          </button>
        </div>
        {erroDrive && <p className="error-text">{erroDrive}</p>}
        {resumo && (
          <div style={{ marginTop: "0.9rem" }}>
            <p className="muted-note" style={{ marginBottom: "0.6rem" }}>
              {resumo.total_processos} processo(s), {resumo.total_embarques} embarque(s),{" "}
              {resumo.total_documentos} documento(s) encontrados.
            </p>
            <div className="doc-list">
              {Object.entries(resumo.documentos_por_tipo).map(([tipo, qtd]) => (
                <span className="doc-chip" key={tipo}>
                  <b>{qtd}</b> {tipo}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>1 · Enviar Razão Contábil do mês</h3>
        <div className="upload-row">
          <input type="file" accept=".csv,.txt" onChange={(e) => setArquivo(e.target.files?.[0] ?? null)} />
          <button className="primary" style={{ marginLeft: "auto" }} onClick={handleProcessar} disabled={processando}>
            {processando ? "Processando..." : "Processar Fechamento"}
          </button>
        </div>
        {mensagem && <p className="muted-note" style={{ marginTop: "0.8rem" }}>{mensagem}</p>}
        {erroRazao && <p className="error-text">{erroRazao}</p>}
        {avisoRateio && <p className="error-text">{avisoRateio}</p>}
        {resumoRazao && (
          <div style={{ marginTop: "0.9rem" }}>
            <p className="muted-note">
              {resumoRazao.total_lancamentos} lançamento(s) importado(s)
              {resumoRazao.mes_referencia ? ` · mês ${resumoRazao.mes_referencia}` : ""} ·{" "}
              {resumoRazao.processos_citados.length} processo(s) citado(s) ·{" "}
              {resumoRazao.lancamentos_multi_processo} candidato(s) a rateio ·{" "}
              {resumoRazao.lancamentos_sem_processo} sem processo identificado.
            </p>
            <div className="doc-list" style={{ marginTop: "0.6rem" }}>
              {Object.entries(resumoRazao.por_categoria).map(([categoria, qtd]) => (
                <span className="doc-chip" key={categoria}>
                  <b>{qtd}</b> {categoria}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Dashboard</h3>
        {indicadores ? (
          <div className="kpi-grid">
            <div className="kpi">
              <div className="num">{indicadores.total_processos}</div>
              <div className="label">Total de processos</div>
            </div>
            <div className="kpi good">
              <div className="num">{indicadores.processos_fechados}</div>
              <div className="label">Fechados</div>
            </div>
            <div className="kpi warn">
              <div className="num">{indicadores.processos_pendentes}</div>
              <div className="label">Pendentes</div>
            </div>
            <div className="kpi bad">
              <div className="num">{indicadores.processos_bloqueados}</div>
              <div className="label">Bloqueados</div>
            </div>
            <div className="kpi">
              <div className="num">R$ {indicadores.valor_total_contabilizado.toFixed(2)}</div>
              <div className="label">Valor contabilizado</div>
            </div>
            <div className="kpi">
              <div className="num">R$ {indicadores.valor_total_rateado.toFixed(2)}</div>
              <div className="label">Valor rateado</div>
            </div>
            <div className="kpi">
              <div className="num">R$ {indicadores.valor_pendente.toFixed(2)}</div>
              <div className="label">Valor pendente</div>
            </div>
            <div className="kpi">
              <div className="num">{indicadores.percentual_automacao.toFixed(1)}%</div>
              <div className="label">Automação</div>
            </div>
          </div>
        ) : (
          <p className="muted-note">Nenhum dado ainda — processe o primeiro fechamento acima.</p>
        )}
      </div>

      <RazaoDashboard mes={mes} />

      <ProcessoTable mes={mes} />

      <CorrectionPanel />
    </div>
  );
}
