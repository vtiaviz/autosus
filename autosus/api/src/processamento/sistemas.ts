/** Os quatro sistemas do processamento e como achar a situação de cada um nos jobs. */

export const SISTEMAS = [
  { id: 'SISAIH01', etapas: ['sisaih01'] },
  { id: 'FPO', etapas: ['fpo'] },
  { id: 'SIHD2', etapas: ['sihd'] },
  { id: 'Transmissor', etapas: ['transmissor_enviar', 'transmissor_testar'] },
] as const;

export const ETAPAS = [
  'iniciar',
  'atualizar',
  'sisaih01',
  'fpo',
  'sihd',
  'transmissor_testar',
  'transmissor_enviar',
] as const;
export type Etapa = (typeof ETAPAS)[number];

export type SituacaoSistema =
  | 'nao_iniciado'
  | 'na_fila'
  | 'executando'
  | 'concluido'
  | 'testado'
  | 'falhou'
  | 'aguardando_decisao'
  | 'cancelado'
  | 'interrompido';

export interface Passo {
  etapa: string;
  args: string[];
  situacao: string;
  inicio?: string;
  fim?: string;
  codigo?: number;
}

export interface JobResumo {
  jobId: string;
  etapas: string[];
  situacao: string;
  passos: Passo[];
  criadoEm: Date;
}

/** Situação de cada sistema pelo job mais recente que o incluiu. */
export function situacaoPorSistema(jobs: JobResumo[]) {
  const recentes = [...jobs].sort((a, b) => b.criadoEm.getTime() - a.criadoEm.getTime());
  return SISTEMAS.map((s) => {
    const job = recentes.find((j) => j.etapas.some((e) => (s.etapas as readonly string[]).includes(e)));
    if (!job) return { sistema: s.id, situacao: 'nao_iniciado' as SituacaoSistema, jobId: null, quando: null };
    const etapa = s.etapas.find((e) => job.etapas.includes(e))!;
    const passos = job.passos.filter((p) => p.etapa === etapa);
    let situacao: SituacaoSistema;
    if (passos.length && passos.every((p) => p.situacao === 'concluido'))
      situacao = etapa === 'transmissor_testar' ? 'testado' : 'concluido';
    else if (passos.some((p) => p.situacao === 'executando')) situacao = 'executando';
    else if (passos.some((p) => p.situacao === 'aguardando_decisao')) situacao = 'aguardando_decisao';
    else if (passos.some((p) => p.situacao === 'falhou')) situacao = 'falhou';
    else if (passos.some((p) => p.situacao === 'cancelado')) situacao = 'cancelado';
    else if (job.situacao === 'na_fila' || job.situacao === 'executando') situacao = 'na_fila';
    // o job acabou antes de chegar nesta etapa (falhou, cancelou ou parou numa decisão)
    else situacao = job.situacao === 'interrompido' ? 'interrompido' : 'cancelado';
    const quando = passos.map((p) => p.fim ?? p.inicio).filter(Boolean).pop() ?? null;
    return { sistema: s.id, situacao, jobId: job.jobId, quando };
  });
}
