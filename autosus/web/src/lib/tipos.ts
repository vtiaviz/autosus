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

export interface Passo {
  etapa: string;
  args: string[];
  situacao: string;
  inicio?: string;
  fim?: string;
  codigo?: number;
}

export interface SistemaSituacao {
  sistema: 'SISAIH01' | 'FPO' | 'SIHD2' | 'Transmissor';
  situacao: string;
  jobId: string | null;
  quando: string | null;
}

export interface Processamento {
  id: number;
  aaaamm: string;
  jobId: string;
  etapas: string[];
  modoEnvio: 'manual' | 'automatico';
  situacao: string;
  mensagem: string | null;
  passos: Passo[];
  imagens: string[];
  criadoEm: string;
  inicio: string | null;
  fim: string | null;
}

export interface ArquivoServidor {
  nome: string;
  tamanho: number;
  modificado: string;
}

export interface PainelProcessamento {
  aaaamm: string;
  apresentacao: string;
  sistemas: SistemaSituacao[];
  processamentos: Processamento[];
  progresso: string | null;
  entrada: {
    completo: boolean;
    itens: { item: string; arquivo: ArquivoServidor | null }[];
    programas: ArquivoServidor[];
  } | null;
  saidas: { arquivos: (ArquivoServidor & { sha256: string })[] } | null;
}

export interface Servidor {
  online: boolean;
  erro?: string;
  vm?: { estado: string; espaco_livre_disco_vm_gb: number; disco_vm: string; snapshots: string[]; versoes_instaladas: Record<string, string> };
  agente?: { vivo: boolean; versao: string | null; ultimo_sinal_segundos: number | null };
}

export const ROTULO_SISTEMA: Record<string, [string, string]> = {
  nao_iniciado: ['Não iniciado', 'neutra'],
  na_fila: ['Na fila', 'neutra'],
  executando: ['Executando', 'aberta'],
  concluido: ['Concluído', 'ok'],
  testado: ['Conexão testada', 'pendente'],
  falhou: ['Falhou', 'erro'],
  aguardando_decisao: ['Com críticas', 'pendente'],
  cancelado: ['Não executado', 'neutra'],
  interrompido: ['Interrompido', 'erro'],
  pendente: ['Pendente', 'neutra'],
};

export const ROTULO_ETAPA: Record<string, string> = {
  iniciar: 'Ligar servidor',
  atualizar: 'Atualizar sistemas',
  sisaih01: 'SISAIH01',
  fpo: 'FPO',
  sihd: 'SIHD2',
  transmissor_testar: 'Transmissor (testar conexão)',
  transmissor_enviar: 'Transmissor (enviar)',
};
