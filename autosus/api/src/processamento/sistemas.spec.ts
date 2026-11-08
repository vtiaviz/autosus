import { JobResumo, situacaoPorSistema } from './sistemas';

const job = (jobId: string, minuto: number, etapas: string[], situacao: string, passos: [string, string][]): JobResumo => ({
  jobId,
  etapas,
  situacao,
  criadoEm: new Date(2026, 10, 7, 10, minuto),
  passos: passos.map(([etapa, s]) => ({ etapa, args: [], situacao: s })),
});

describe('situacaoPorSistema', () => {
  it('sem jobs, nada iniciado', () => {
    expect(situacaoPorSistema([]).map((s) => s.situacao)).toEqual([
      'nao_iniciado', 'nao_iniciado', 'nao_iniciado', 'nao_iniciado',
    ]);
  });

  it('usa o job mais recente de cada sistema', () => {
    const r = situacaoPorSistema([
      job('a', 1, ['sisaih01', 'fpo'], 'falhou', [['sisaih01', 'concluido'], ['fpo', 'falhou']]),
      job('b', 2, ['fpo', 'sihd'], 'executando', [['fpo', 'concluido'], ['sihd', 'executando']]),
    ]);
    expect(r.map((s) => [s.sistema, s.situacao, s.jobId])).toEqual([
      ['SISAIH01', 'concluido', 'a'],
      ['FPO', 'concluido', 'b'],
      ['SIHD2', 'executando', 'b'],
      ['Transmissor', 'nao_iniciado', null],
    ]);
  });

  it('SIHD2 com críticas e o envio que não chegou a rodar', () => {
    const r = situacaoPorSistema([
      job('c', 3, ['sihd', 'transmissor_enviar'], 'aguardando_decisao', [
        ['sihd', 'aguardando_decisao'], ['transmissor_enviar', 'pendente'], ['transmissor_enviar', 'pendente'],
      ]),
    ]);
    expect(r[2].situacao).toBe('aguardando_decisao');
    expect(r[3].situacao).toBe('cancelado');
  });

  it('teste de conexão aparece como testado, não como enviado', () => {
    const r = situacaoPorSistema([
      job('d', 4, ['transmissor_testar'], 'concluido', [['transmissor_testar', 'concluido'], ['transmissor_testar', 'concluido']]),
    ]);
    expect(r[3].situacao).toBe('testado');
  });

  it('etapas ainda na fila', () => {
    const r = situacaoPorSistema([job('e', 5, ['fpo'], 'na_fila', [['fpo', 'pendente']])]);
    expect(r[1].situacao).toBe('na_fila');
  });
});
