import { HttpException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { openAsBlob } from 'node:fs';
import { basename } from 'node:path';

/** Cliente da API do Server_SUS (server_sus/api). O token nunca vai para o navegador. */
@Injectable()
export class ServidorService {
  private readonly url: string;
  private readonly token: string;

  constructor(config: ConfigService) {
    this.url = (config.get<string>('SERVER_SUS_URL') ?? 'http://127.0.0.1:8765').replace(/\/$/, '');
    this.token = config.get<string>('SERVER_SUS_TOKEN') ?? '';
  }

  private async chamar(caminho: string, init: RequestInit = {}, timeoutMs = 30_000): Promise<Response> {
    if (!this.token) throw new ServiceUnavailableException('SERVER_SUS_TOKEN não configurado no .env da API');
    let resp: Response;
    try {
      resp = await fetch(`${this.url}${caminho}`, {
        ...init,
        headers: { Authorization: `Bearer ${this.token}`, ...(init.headers ?? {}) },
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch {
      throw new ServiceUnavailableException(
        'o Server_SUS não respondeu; confira se a API dele está rodando (server_sus\\api.bat)',
      );
    }
    if (!resp.ok) {
      let detalhe = `Server_SUS respondeu ${resp.status}`;
      try {
        const corpo = (await resp.json()) as { detail?: unknown };
        if (typeof corpo.detail === 'string') detalhe = corpo.detail;
        else if (corpo.detail) detalhe = JSON.stringify(corpo.detail);
      } catch {
        /* sem JSON */
      }
      throw new HttpException(detalhe, resp.status >= 500 ? 502 : resp.status);
    }
    return resp;
  }

  async json<T>(caminho: string, init: RequestInit = {}, timeoutMs?: number): Promise<T> {
    const resp = await this.chamar(
      caminho,
      { ...init, headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) } },
      timeoutMs,
    );
    return (await resp.json()) as T;
  }

  async binario(caminho: string): Promise<{ tipo: string; dados: Buffer }> {
    const resp = await this.chamar(caminho);
    return { tipo: resp.headers.get('content-type') ?? 'application/octet-stream', dados: Buffer.from(await resp.arrayBuffer()) };
  }

  /** Envia um arquivo para a competência no Server_SUS, com o SHA-256 para conferência. */
  async enviarArquivo(aaaamm: string, caminho: string, sha256?: string | null) {
    const form = new FormData();
    form.append('arquivo', await openAsBlob(caminho), basename(caminho));
    if (sha256) form.append('sha256', sha256);
    return (await (await this.chamar(`/competencias/${aaaamm}/arquivos`, { method: 'POST', body: form }, 600_000)).json()) as {
      nome: string;
      situacao: 'novo' | 'ja_existe' | 'substituido';
      sha256: string;
      tamanho: number;
    };
  }
}
