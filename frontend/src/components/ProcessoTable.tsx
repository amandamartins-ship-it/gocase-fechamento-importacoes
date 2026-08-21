import { Fragment, useEffect, useState } from "react";
import { api, FechamentoProcesso, LinhasRateadasProcesso, MemoriaRateio, ProcessoResumo } from "../api/client";
import RateioDetailModal from "./RateioDetailModal";

function StatusPill({ status }: { status: string | null }) {
  if (!status) return <span className="muted-note">—</span>;
  const classe = status === "Fechado" ? "good" : status === "Pendente" ? "warn" : status === "Bloqueado" ? "bad" : "";
  return <span className={`pill ${classe}`}>{status}</span>;
}

/** Linhas do processo já rateadas, no mesmo formato de "Processos Fechados":
 * uma linha por processo participante, com débito/crédito já divididos, mais
 * o rodapé de totais e saldo do processo. */
function LinhasRateadas({ codigo, mes }: { codigo: string; mes: string }) {
  const [dados, setDados] = useState<LinhasRateadasProcesso | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [memoria, setMemoria] = useState<MemoriaRateio | null>(null);

  useEffect(() => {
    api
      .linhasRateadas(codigo, mes)
      .then(setDados)
      .catch((err) => setErro(err instanceof Error ? err.message : "Falha ao carregar as linhas do processo"));
  }, [codigo, mes]);

  async function verRateio(lancamentoId: number | null) {
    if (lancamentoId == null) return;
    try {
      const { memoria } = await api.auditoriaRateio(lancamentoId);
      setMemoria(memoria);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Sem memória de cálculo para este lançamento");
    }
  }

  if (erro) return <p className="error-text">{erro}</p>;
  if (!dados) return <p className="muted-note">Carregando linhas do processo...</p>;
  if (dados.linhas.length === 0) return <p className="muted-note">Nenhuma linha rateada neste mês.</p>;

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Conta</th>
            <th>Numero Contabil</th>
            <th>Unidade</th>
            <th>Historico</th>
            <th className="num">Debito</th>
            <th className="num">Credito</th>
            <th className="num">Movimentação</th>
            <th>Processo</th>
            <th>Processo (Controle de Importação)</th>
            <th>Rateio</th>
          </tr>
        </thead>
        <tbody>
          {dados.linhas.map((l, idx) => (
            <tr key={`${l.lancamento_id ?? idx}-${l.processo}`}>
              <td className="code">{l.data ?? "—"}</td>
              <td className="code">{l.conta ?? "—"}</td>
              <td className="code">{l.numero_contabil ?? "—"}</td>
              <td className="code">{l.unidade ?? "—"}</td>
              <td>{l.historico}</td>
              <td className="num">R$ {l.debito.toFixed(2)}</td>
              <td className="num">R$ {l.credito.toFixed(2)}</td>
              <td className="num">R$ {l.movimentacao.toFixed(2)}</td>
              <td className="code">{l.processo}</td>
              <td className="code">{l.processo_controle_importacao}</td>
              <td>
                <button className="ghost" onClick={() => verRateio(l.lancamento_id)}>
                  Ver rateio
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ fontWeight: 600 }}>
            <td colSpan={5}>Total</td>
            <td className="num">R$ {dados.total_debito.toFixed(2)}</td>
            <td className="num">R$ {dados.total_credito.toFixed(2)}</td>
            <td className="num" colSpan={4}>
              Saldo processo: R$ {dados.saldo_processo.toFixed(2)}
            </td>
          </tr>
        </tfoot>
      </table>
      {memoria && <RateioDetailModal memoria={memoria} onClose={() => setMemoria(null)} />}
    </div>
  );
}

/** Compara, por categoria, o que já está contabilizado no Razão com o que os
 * documentos reais (pasta FATURAMENTO FINAL) dizem - a "despesa documentada
 * mas ainda não contabilizada" fica visível como diferença != 0. Nunca
 * inventa valor: sem extração ainda feita, documentado fica 0. */
function ComposicaoDocumentos({ codigo, mes }: { codigo: string; mes: string }) {
  const [fechamento, setFechamento] = useState<FechamentoProcesso | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [semFechamento, setSemFechamento] = useState(false);
  const [extraindo, setExtraindo] = useState(false);

  function carregar() {
    setErro(null);
    setSemFechamento(false);
    api
      .obterFechamentoProcesso(codigo, mes)
      .then(setFechamento)
      .catch((err) => {
        const mensagem = err instanceof Error ? err.message : "Falha ao carregar a composição";
        if (mensagem.includes("Nenhum fechamento processado")) {
          setSemFechamento(true);
        } else {
          setErro(mensagem);
        }
      });
  }

  useEffect(carregar, [codigo, mes]);

  async function extrairValores() {
    setExtraindo(true);
    setErro(null);
    try {
      await api.extrairValoresDocumentos(codigo);
      carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao extrair valores dos documentos");
    } finally {
      setExtraindo(false);
    }
  }

  return (
    <div style={{ marginTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", flexWrap: "wrap", gap: "0.5rem" }}>
        <h4 style={{ margin: 0 }}>Composição contábil × documentos</h4>
        <button className="ghost" onClick={extrairValores} disabled={extraindo}>
          {extraindo ? "Extraindo..." : "Extrair valores dos documentos"}
        </button>
      </div>
      {erro && <p className="error-text">{erro}</p>}
      {semFechamento && <p className="muted-note">Este processo ainda não teve o fechamento processado neste mês.</p>}
      {!erro && !semFechamento && !fechamento && <p className="muted-note">Carregando...</p>}
      {fechamento && fechamento.composicao.length === 0 && (
        <p className="muted-note">Nenhuma categoria de despesa encontrada.</p>
      )}
      {fechamento && fechamento.composicao.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Categoria</th>
                <th className="num">Contabilizado (Razão)</th>
                <th className="num">Documentado (Drive)</th>
                <th className="num">Diferença</th>
              </tr>
            </thead>
            <tbody>
              {fechamento.composicao.map((item) => (
                <tr key={item.categoria}>
                  <td>{item.categoria}</td>
                  <td className="num">R$ {item.valor_contabilizado.toFixed(2)}</td>
                  <td className="num">R$ {item.valor_documentos.toFixed(2)}</td>
                  <td className="num" style={item.diferenca !== 0 ? { color: "var(--warn)", fontWeight: 600 } : undefined}>
                    R$ {item.diferenca.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function ProcessoTable({ mes }: { mes: string }) {
  const [processos, setProcessos] = useState<ProcessoResumo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [expandido, setExpandido] = useState<string | null>(null);
  const [baixando, setBaixando] = useState<string | null>(null);

  function carregar() {
    setErro(null);
    api
      .listarProcessos(mes)
      .then(setProcessos)
      .catch((err) => setErro(err instanceof Error ? err.message : "Falha ao carregar processos"));
  }

  useEffect(carregar, [mes]);

  async function baixar(tipo: "razao" | "fechados") {
    setBaixando(tipo);
    setErro(null);
    try {
      if (tipo === "razao") {
        await api.baixarRazaoAtualizado(mes);
      } else {
        await api.baixarProcessosFechados(mes);
      }
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao gerar o arquivo");
    } finally {
      setBaixando(null);
    }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.9rem", flexWrap: "wrap", gap: "0.6rem" }}>
        <h3 style={{ margin: 0 }}>Processos {mes ? `— ${mes.slice(0, 7)}` : ""}</h3>
        <div className="row">
          <button className="ghost" onClick={() => baixar("razao")} disabled={baixando !== null}>
            {baixando === "razao" ? "Gerando..." : "Baixar Razão Atualizado"}
          </button>
          <button className="ghost" onClick={() => baixar("fechados")} disabled={baixando !== null}>
            {baixando === "fechados" ? "Gerando..." : "Baixar Processos Fechados"}
          </button>
          <button className="ghost" onClick={carregar}>
            Atualizar
          </button>
        </div>
      </div>
      {erro && <p className="error-text">{erro}</p>}
      {!processos ? (
        <p className="muted-note">Carregando...</p>
      ) : processos.length === 0 ? (
        <p className="muted-note">Nenhum processo sincronizado ainda — conecte e sincronize o Drive acima.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Processo</th>
                <th>Empresa</th>
                <th>Descrição</th>
                <th>Status</th>
                <th className="num">Saldo final</th>
              </tr>
            </thead>
            <tbody>
              {processos.map((p) => (
                <Fragment key={p.codigo}>
                  <tr style={{ cursor: "pointer" }} onClick={() => setExpandido(expandido === p.codigo ? null : p.codigo)}>
                    <td className="code">{p.codigo}</td>
                    <td>{p.empresa_codigo}</td>
                    <td>{p.descricao ?? "—"}</td>
                    <td>
                      <StatusPill status={p.status} />
                    </td>
                    <td className="num">{p.saldo_final != null ? `R$ ${p.saldo_final.toFixed(2)}` : "—"}</td>
                  </tr>
                  {expandido === p.codigo && (
                    <tr>
                      <td colSpan={5} style={{ background: "var(--paper)", padding: "0.9rem" }}>
                        <LinhasRateadas codigo={p.codigo} mes={mes} />
                        <ComposicaoDocumentos codigo={p.codigo} mes={mes} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
