export type SituacaoCompetencia = 'aguardando' | 'aberta' | 'encerrada' | 'sem_datas';

export interface Competencia {
  aaaamm: string;
  apresentacao: string;
  abertura: string | null;
  fechamento: string | null;
  datas: { rotulo: string; data: string }[];
  situacao: SituacaoCompetencia;
  arquivos: { baixados: number; pendentes: number };
  programas: { baixados: number; pendentes: number };
}

export interface ItemAtualizacao {
  id: number;
  nome: string;
  tipo: 'arquivo' | 'programa';
  situacao: 'baixado' | 'ja_existe' | 'pendente' | 'erro' | 'simulado' | string;
  arquivo: string;
  versao: string;
  detalhe: string;
  tamanho: number;
  sha256: string | null;
  revisaoNova: boolean;
  verificadoEm: string;
  enviadoEm: string | null;
}

export interface Atualizacoes {
  aaaamm: string;
  pasta: string;
  verificadoEm: string | null;
  arquivos: ItemAtualizacao[];
  programas: ItemAtualizacao[];
  execucao: {
    id: number;
    inicio: string;
    fim: string | null;
    codigo: number | null;
    saida: string;
    emAndamento: boolean;
  } | null;
}

export const ROTULO_SITUACAO_COMPETENCIA: Record<SituacaoCompetencia, [string, string]> = {
  aguardando: ['Aguardando abertura', 'neutra'],
  aberta: ['Aberta', 'aberta'],
  encerrada: ['Encerrada', 'neutra'],
  sem_datas: ['Sem datas', 'neutra'],
};

export function rotuloItem(situacao: string): [string, string] {
  switch (situacao) {
    case 'baixado':
      return ['Baixado', 'ok'];
    case 'ja_existe':
      return ['Baixado', 'ok'];
    case 'pendente':
      return ['Pendente', 'pendente'];
    case 'erro':
      return ['Erro', 'erro'];
    default:
      return [situacao, 'neutra'];
  }
}
