import { useEffect, useState } from "react";
import { api, CATEGORIAS_LANCAMENTO, RegraAprendida, TIPOS_DOCUMENTO } from "../api/client";

export default function CorrectionPanel() {
  const [tipo, setTipo] = useState<"classificacao" | "documento">("classificacao");
  const [padrao, setPadrao] = useState("");
  const [valorCorrigido, setValorCorrigido] = useState(CATEGORIAS_LANCAMENTO[0]);
  const [justificativa, setJustificativa] = useState("");
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [regras, setRegras] = useState<RegraAprendida[] | null>(null);

  function carregarRegras() {
    api
      .listarRegras()
      .then(setRegras)
      .catch(() => setRegras(null));
  }

  useEffect(carregarRegras, []);

  function handleTipoChange(novoTipo: "classificacao" | "documento") {
    setTipo(novoTipo);
    setValorCorrigido(novoTipo === "classificacao" ? CATEGORIAS_LANCAMENTO[0] : TIPOS_DOCUMENTO[0]);
  }

  async function handleSalvar() {
    setErro(null);
    setMensagem(null);
    if (!padrao.trim()) {
      setErro("Informe o trecho do histórico (ou nome de arquivo) que identifica os casos a corrigir.");
      return;
    }
    try {
      const resultado = await api.corrigir({
        tipo,
        padrao: padrao.trim(),
        valor_corrigido: valorCorrigido,
        justificativa: justificativa.trim() || undefined,
      });
      setMensagem(resultado.mensagem);
      setPadrao("");
      setJustificativa("");
      carregarRegras();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao salvar a correção");
    }
  }

  const opcoes = tipo === "classificacao" ? CATEGORIAS_LANCAMENTO : TIPOS_DOCUMENTO;

  return (
    <div className="card">
      <h3>Correções (motor de aprendizado)</h3>
      <p className="muted-note" style={{ marginTop: "-0.4rem", marginBottom: "1rem" }}>
        Corrija a classificação de um lançamento (por um trecho do histórico) ou de um documento (por um trecho do
        nome do arquivo). A correção vale a partir do próximo upload do Razão ou sincronização do Drive.
      </p>

      <div className="field">
        <label>O que corrigir</label>
        <select value={tipo} onChange={(e) => handleTipoChange(e.target.value as "classificacao" | "documento")}>
          <option value="classificacao">Categoria de lançamento (Razão)</option>
          <option value="documento">Tipo de documento (Drive)</option>
        </select>
      </div>
      <div className="field">
        <label>{tipo === "classificacao" ? "Trecho do histórico" : "Trecho do nome do arquivo"}</label>
        <input value={padrao} onChange={(e) => setPadrao(e.target.value)} placeholder="ex: TAXA XPTO" />
      </div>
      <div className="field">
        <label>Valor correto</label>
        <select value={valorCorrigido} onChange={(e) => setValorCorrigido(e.target.value)}>
          {opcoes.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>Justificativa (opcional)</label>
        <input value={justificativa} onChange={(e) => setJustificativa(e.target.value)} />
      </div>
      <button className="primary" onClick={handleSalvar}>
        Salvar correção
      </button>
      {mensagem && <p className="muted-note" style={{ marginTop: "0.6rem" }}>{mensagem}</p>}
      {erro && <p className="error-text">{erro}</p>}

      {regras && regras.length > 0 && (
        <div style={{ marginTop: "1.4rem" }}>
          <h3>Correções já registradas</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Padrão</th>
                  <th>Valor corrigido</th>
                  <th>Por</th>
                </tr>
              </thead>
              <tbody>
                {regras.map((r) => (
                  <tr key={r.id}>
                    <td>{r.tipo}</td>
                    <td>{r.padrao}</td>
                    <td>{r.valor_corrigido}</td>
                    <td className="muted-note">{r.criado_por ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
