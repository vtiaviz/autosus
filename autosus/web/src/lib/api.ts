'use client';

export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

/** Chamada à API do AutoSUS. Sessão expirada (401) volta para o login. */
export async function api<T>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api${caminho}`, {
    ...opcoes,
    headers: { 'Content-Type': 'application/json', ...(opcoes.headers ?? {}) },
    credentials: 'same-origin',
  });
  if (resp.status === 401 && !caminho.startsWith('/auth/entrar')) {
    window.location.href = '/login';
    throw new ErroApi(401, 'sessão expirada');
  }
  if (!resp.ok) {
    let mensagem = `erro ${resp.status}`;
    try {
      const corpo = await resp.json();
      mensagem = Array.isArray(corpo.message) ? corpo.message.join('; ') : (corpo.message ?? mensagem);
    } catch {
      /* resposta sem JSON */
    }
    throw new ErroApi(resp.status, mensagem);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

export function rotuloCompetencia(aaaamm: string): string {
  return `${aaaamm.slice(4)}/${aaaamm.slice(0, 4)}`;
}

export function dataBR(iso: string | null | undefined): string {
  if (!iso) return '-';
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
}

export function dataHoraBR(iso: string | null | undefined): string {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export function tamanho(bytes: number): string {
  if (!bytes) return '-';
  const unidades = ['B', 'KB', 'MB', 'GB'];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < unidades.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(i ? 1 : 0)} ${unidades[i]}`;
}
