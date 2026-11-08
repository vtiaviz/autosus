/** Competência no formato AAAAMM (ex.: 202608). */
export const PADRAO_COMPETENCIA = /^20\d{2}(0[1-9]|1[0-2])$/;

/** Competência + 1 mês: a apresentação do SISAIH01/WebAIH. */
export function apresentacao(aaaamm: string): string {
  const ano = Number(aaaamm.slice(0, 4));
  const mes = Number(aaaamm.slice(4));
  return mes === 12 ? `${ano + 1}01` : `${ano}${String(mes + 1).padStart(2, '0')}`;
}

/** Mês anterior ao de hoje: a competência que o downloader busca por padrão. */
export function competenciaPadrao(hoje = new Date()): string {
  const d = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export function rotulo(aaaamm: string): string {
  return `${aaaamm.slice(4)}/${aaaamm.slice(0, 4)}`;
}
