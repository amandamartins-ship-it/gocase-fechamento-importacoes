import { MemoriaRateio } from "../api/client";

export default function RateioDetailModal({
  memoria,
  onClose,
}: {
  memoria: MemoriaRateio;
  onClose: () => void;
}) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(20, 22, 28, 0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card"
        style={{ maxWidth: 520, width: "90%", maxHeight: "80vh", overflowY: "auto" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <h2 style={{ marginTop: 0 }}>Memória de cálculo do rateio</h2>
          <button className="ghost" onClick={onClose}>
            Fechar
          </button>
        </div>
        <p className="muted-note">{memoria.historico}</p>
        <p className="muted-note">
          NF utilizada: {memoria.nf_utilizada} · {memoria.quantidade_total_itens_nf} itens no total · fonte:{" "}
          {memoria.fonte}
        </p>
        <p className="muted-note">
          Valor original: débito R$ {memoria.valor_debito_original} · crédito R$ {memoria.valor_credito_original}
        </p>
        <div className="table-wrap" style={{ marginTop: "0.6rem" }}>
          <table>
            <thead>
              <tr>
                <th>Processo</th>
                <th className="num">Itens</th>
                <th className="num">%</th>
                <th className="num">Débito destinado</th>
                <th className="num">Crédito destinado</th>
              </tr>
            </thead>
            <tbody>
              {memoria.participantes.map((p) => (
                <tr key={p.processo}>
                  <td className="code">{p.processo}</td>
                  <td className="num">{p.quantidade_itens}</td>
                  <td className="num">{(Number(p.percentual) * 100).toFixed(1)}%</td>
                  <td className="num">R$ {p.valor_debito_destinado}</td>
                  <td className="num">R$ {p.valor_credito_destinado}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted-note" style={{ marginTop: "0.8rem" }}>
          Fórmula: {memoria.formula}
        </p>
      </div>
    </div>
  );
}
