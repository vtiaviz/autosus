const PASSOS = [
  ['power_settings_new', 'Ligar servidor', 'Liga a VM do Server_SUS e espera o agente responder'],
  ['system_update_alt', 'Atualizar sistemas', 'Instala as versões novas baixadas pelo AutoSUS'],
  ['description', 'SISAIH01', 'Importa a produção do WebAIH, consiste, apura e exporta'],
  ['payments', 'FPO', 'Importa BDSIA e CNES, aplica valores vigentes e exporta o .VTP'],
  ['fact_check', 'SIHD2', 'Importa CNES, tabelas e AIHs, critica, apura e encerra (.DTS)'],
  ['send', 'Transmissor', 'Envia o .DTS ao DATASUS (manual ou automático sem críticas)'],
];

export default function Processamento() {
  return (
    <>
      <div className="pagina-cabecalho">
        <div>
          <h3>Processamento AIH</h3>
          <p>Os botões chegam na etapa 5, ligados aos jobs do Server_SUS (já prontos na API dele).</p>
        </div>
      </div>
      <div className="cad-card">
        <div className="tabela-rolagem">
          <table className="sus-table">
            <thead><tr><th></th><th>Passo</th><th>O que faz</th><th>Situação</th></tr></thead>
            <tbody>
              {PASSOS.map(([icone, titulo, texto]) => (
                <tr key={titulo}>
                  <td><span className="material-symbols-outlined" style={{ color: 'var(--primary)' }}>{icone}</span></td>
                  <td className="cod">{titulo}</td>
                  <td>{texto}</td>
                  <td><span className="situacao neutra">Etapa 5</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
