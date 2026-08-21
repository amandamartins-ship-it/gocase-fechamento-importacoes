import { useEffect, useState } from "react";
import { api, ProcessoResumo } from "../api/client";

export interface ResumoRazaoMes {
  total_debitos: number;
  total_creditos: number;
  processos_movimentados: string[];
  total_processos: number;
}

export default function RazaoDashboard({ mes }: { mes: string }) {
  const [resumo, setResumo] = useState<ResumoRazaoMes | null>(null);
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    if (!mes) return;

    setCarregando(true);
    api
      .listarProcessos(mes)
      .then((processos: ProcessoResumo[]) => {
        // Agregar dados dos processos
        let totalDebitos = 0;
        let totalCreditos = 0;
        const processosComMovimento = new Set<string>();

        processos.forEach((p) => {
          if (p.saldo_final !== null && p.saldo_final !== 0) {
            processosComMovimento.add(p.codigo);
            // Usar saldo_final como aproximação de débitos
            if (p.saldo_final > 0) {
              totalDebitos += p.saldo_final;
            } else {
              totalCreditos += Math.abs(p.saldo_final);
            }
          }
        });

        setResumo({
          total_debitos: totalDebitos,
          total_creditos: totalCreditos,
          processos_movimentados: Array.from(processosComMovimento).sort(),
          total_processos: processosComMovimento.size,
        });
      })
      .catch(() => setResumo(null))
      .finally(() => setCarregando(false));
  }, [mes]);

  const saldo = (resumo?.total_debitos ?? 0) - (resumo?.total_creditos ?? 0);
  const temDados = resumo && (resumo.total_debitos > 0 || resumo.total_creditos > 0);

  return (
    <div className="card">
      <h3>📊 Resumo do Razão {mes ? `— ${mes.slice(0, 7)}` : ""}</h3>

      {carregando ? (
        <p className="muted-note">Carregando dados...</p>
      ) : !temDados ? (
        <p className="muted-note">Nenhuma movimentação registrada neste mês.</p>
      ) : (
        <div className="kpi-grid">
          <div className="kpi">
            <div className="num">{resumo?.total_processos}</div>
            <div className="label">Processos movimentados</div>
          </div>
          <div className="kpi">
            <div className="num">R$ {(resumo?.total_debitos ?? 0).toFixed(2)}</div>
            <div className="label">Total de Débitos</div>
          </div>
          <div className="kpi">
            <div className="num">R$ {(resumo?.total_creditos ?? 0).toFixed(2)}</div>
            <div className="label">Total de Créditos</div>
          </div>
          <div className={`kpi ${Math.abs(saldo) > 0.01 ? "warn" : "good"}`}>
            <div className="num">R$ {saldo.toFixed(2)}</div>
            <div className="label">Saldo (Diferença)</div>
          </div>
        </div>
      )}

      {resumo && resumo.processos_movimentados.length > 0 && (
        <div style={{ marginTop: "1.4rem" }}>
          <h4 style={{ margin: "0 0 0.8rem 0" }}>Processos com movimentação:</h4>
          <div className="doc-list">
            {resumo.processos_movimentados.slice(0, 20).map((proc) => (
              <span className="doc-chip" key={proc}>
                {proc}
              </span>
            ))}
            {resumo.processos_movimentados.length > 20 && (
              <span className="doc-chip" style={{ opacity: 0.6 }}>
                +{resumo.processos_movimentados.length - 20} mais
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
