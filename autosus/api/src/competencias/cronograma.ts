/**
 * Leitura do cronograma de competências do CNES/SIA/SIH:
 * https://wiki.saude.gov.br/cnes/index.php/Cronograma
 *
 * A página tem uma tabela por ano ("CRONOGRAMA 2026"), uma linha por mês e 9 datas em cada linha.
 * Abertura = "Disponibilização dos aplicativos de processamento" e
 * fechamento = "Envio da remessa do SIA/SIH" (decisão do Victor em 07/11/2026).
 */

export const URL_CRONOGRAMA = 'https://wiki.saude.gov.br/cnes/index.php/Cronograma';

export interface DataCronograma {
  rotulo: string;
  data: string; // AAAA-MM-DD
}

export interface LinhaCronograma {
  aaaamm: string;
  datas: DataCronograma[];
  abertura?: string;
  fechamento?: string;
}

const MESES = [
  'JANEIRO', 'FEVEREIRO', 'MARCO', 'ABRIL', 'MAIO', 'JUNHO',
  'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO',
];

const ABERTURA = 'APLICATIVOS DE PROCESSAMENTO';
const FECHAMENTO = 'REMESSA DO SIA/SIH';

function texto(html: string): string {
  return html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizar(t: string): string {
  return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
}

function isoDe(ddmmaaaa: string): string | undefined {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(ddmmaaaa);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : undefined;
}

/** Extrai todas as linhas de todos os anos da página. */
export function lerCronograma(html: string): LinhaCronograma[] {
  const linhas: LinhaCronograma[] = [];
  for (const tabela of html.match(/<table[\s\S]*?<\/table>/gi) ?? []) {
    let ano: string | undefined;
    let rotulos: string[] = [];
    for (const tr of tabela.match(/<tr[\s\S]*?<\/tr>/gi) ?? []) {
      const celulas = (tr.match(/<t[hd][^>]*>[\s\S]*?(?=<t[hd][^>]*>|<\/tr>)/gi) ?? []).map(texto);
      const titulo = /CRONOGRAMA\s+(\d{4})/i.exec(celulas.join(' '));
      if (titulo) {
        ano = titulo[1];
        continue;
      }
      if (normalizar(celulas[0] ?? '') === 'COMPETENCIA') {
        rotulos = celulas.slice(1).map((r) => r.replace(/\*+/g, '').trim());
        continue;
      }
      const mes = MESES.indexOf(normalizar(celulas[0] ?? ''));
      if (!ano || mes < 0 || rotulos.length === 0) continue;
      const datas: DataCronograma[] = [];
      celulas.slice(1).forEach((c, i) => {
        const data = isoDe(c);
        if (data && rotulos[i]) datas.push({ rotulo: rotulos[i], data });
      });
      const achar = (chave: string) =>
        datas.find((d) => normalizar(d.rotulo).includes(chave))?.data;
      linhas.push({
        aaaamm: `${ano}${String(mes + 1).padStart(2, '0')}`,
        datas,
        abertura: achar(ABERTURA),
        fechamento: achar(FECHAMENTO),
      });
    }
  }
  return linhas;
}

export type SituacaoCompetencia = 'aguardando' | 'aberta' | 'encerrada' | 'sem_datas';

/** Situação da competência numa data (padrão: hoje), pelas datas de abertura e fechamento. */
export function situacao(
  abertura: Date | null,
  fechamento: Date | null,
  hoje = new Date(),
): SituacaoCompetencia {
  if (!abertura || !fechamento) return 'sem_datas';
  const dia = hoje.toISOString().slice(0, 10);
  if (dia < abertura.toISOString().slice(0, 10)) return 'aguardando';
  if (dia > fechamento.toISOString().slice(0, 10)) return 'encerrada';
  return 'aberta';
}
