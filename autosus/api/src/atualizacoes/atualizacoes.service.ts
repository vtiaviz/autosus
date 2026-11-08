import {
  ConflictException,
  Injectable,
  Logger,
  OnApplicationBootstrap,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Interval, SchedulerRegistry } from '@nestjs/schedule';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { readdir, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { CronJob } from 'cron';
import { competenciaPadrao } from '../comum/competencia';
import { CompetenciasService } from '../competencias/competencias.service';
import { PrismaService } from '../prisma/prisma.service';

/** O que o downloader grava em autosus/downloads/estado/AAAAMM.json (opção --json). */
export interface EstadoDownloader {
  competencia: string;
  pasta: string;
  simulado: boolean;
  gerado_em: string;
  itens: {
    nome: string;
    tipo: 'arquivo' | 'programa';
    situacao: string;
    arquivo: string;
    detalhe: string;
    revisao_nova: boolean;
    tamanho: number;
    sha256: string | null;
    versao: string;
  }[];
}

const LINHAS_GUARDADAS = 200;

@Injectable()
export class AtualizacoesService implements OnApplicationBootstrap {
  private readonly log = new Logger('Atualizacoes');
  readonly pastaDownloads: string;
  readonly python: string;
  private emAndamento: { aaaamm: string; execucao: number } | null = null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly competencias: CompetenciasService,
    private readonly agenda: SchedulerRegistry,
    config: ConfigService,
  ) {
    this.pastaDownloads = resolve(
      config.get<string>('AUTOSUS_DOWNLOADS') ?? join(process.cwd(), '..', 'downloads'),
    );
    this.python = resolve(
      config.get<string>('PYTHON') ??
        join(this.pastaDownloads, '..', '..', '.venv', 'Scripts', 'python.exe'),
    );
    const cron = config.get<string>('ATUALIZACOES_AGENDA');
    if (cron) {
      // substitui a tarefa agendada do Windows quando o AutoSUS roda como serviço
      const job = new CronJob(cron, () => {
        this.verificar(competenciaPadrao()).catch((e: Error) => this.log.warn(e.message));
      });
      this.agenda.addCronJob('downloader', job);
      job.start();
      this.log.log(`downloader agendado: ${cron}`);
    }
  }

  async onApplicationBootstrap() {
    await this.importarTodos();
  }

  /** A tarefa agendada do Windows e o autosus.bat também gravam estado/*.json: lê de tempos em tempos. */
  @Interval(5 * 60_000)
  async importarTodos() {
    const pasta = join(this.pastaDownloads, 'estado');
    if (!existsSync(pasta)) return;
    for (const nome of await readdir(pasta)) {
      const m = /^(\d{6})\.json$/.exec(nome);
      if (m) await this.importar(m[1]).catch((e: Error) => this.log.warn(`${nome}: ${e.message}`));
    }
  }

  /** Grava no banco o resultado da última execução do downloader, se for mais novo que o do banco. */
  async importar(aaaamm: string): Promise<boolean> {
    const arq = join(this.pastaDownloads, 'estado', `${aaaamm}.json`);
    if (!existsSync(arq)) return false;
    const estado = JSON.parse(await readFile(arq, 'utf-8')) as EstadoDownloader;
    if (estado.simulado || estado.competencia !== aaaamm) return false;
    const gerado = new Date(estado.gerado_em);
    const ultimo = await this.prisma.itemAtualizacao.aggregate({
      where: { aaaamm },
      _max: { verificadoEm: true },
    });
    if (ultimo._max.verificadoEm && ultimo._max.verificadoEm >= gerado) return false;
    await this.competencias.garantir(aaaamm);
    for (const i of estado.itens) {
      const dados = {
        tipo: i.tipo,
        situacao: i.situacao,
        arquivo: i.arquivo ?? '',
        versao: i.versao ?? '',
        detalhe: i.detalhe ?? '',
        tamanho: BigInt(i.tamanho ?? 0),
        sha256: i.sha256,
        revisaoNova: !!i.revisao_nova,
        verificadoEm: gerado,
      };
      await this.prisma.itemAtualizacao.upsert({
        where: { aaaamm_nome: { aaaamm, nome: i.nome } },
        create: { aaaamm, nome: i.nome, ...dados },
        update: dados,
      });
    }
    return true;
  }

  /** Onde o downloader guarda os arquivos (config.yaml > pasta_destino), como ele mesmo informou. */
  async pastaDestino(aaaamm: string): Promise<string> {
    const pasta = join(this.pastaDownloads, 'estado');
    if (!existsSync(pasta)) return '';
    const outros = (await readdir(pasta)).filter((n) => /^\d{6}\.json$/.test(n)).sort().reverse();
    // o da própria competência; senão, o de qualquer execução (a pasta é a mesma para todas)
    for (const nome of [`${aaaamm}.json`, ...outros]) {
      const arq = join(pasta, nome);
      if (!existsSync(arq)) continue;
      const estado = JSON.parse(await readFile(arq, 'utf-8')) as EstadoDownloader;
      if (estado.pasta) return estado.pasta;
    }
    return '';
  }

  async obter(aaaamm: string) {
    await this.importar(aaaamm);
    const itens = await this.prisma.itemAtualizacao.findMany({
      where: { aaaamm },
      orderBy: [{ tipo: 'asc' }, { nome: 'asc' }],
    });
    const execucao = await this.prisma.execucaoDownload.findFirst({
      where: { aaaamm },
      orderBy: { inicio: 'desc' },
    });
    const lista = itens.map((i) => ({ ...i, tamanho: Number(i.tamanho) }));
    return {
      aaaamm,
      pasta: await this.pastaDestino(aaaamm),
      verificadoEm: itens.reduce<Date | null>(
        (max, i) => (!max || i.verificadoEm > max ? i.verificadoEm : max),
        null,
      ),
      arquivos: lista.filter((i) => i.tipo === 'arquivo'),
      programas: lista.filter((i) => i.tipo === 'programa'),
      execucao: execucao && {
        ...execucao,
        emAndamento: this.emAndamento?.execucao === execucao.id,
      },
    };
  }

  /** Aviso pelo Windows e por e-mail, com a mesma configuração do downloader (config.yaml e .env dele). */
  avisar(titulo: string, texto: string): Promise<boolean> {
    return new Promise((ok) => {
      const proc = spawn(this.python, ['-m', 'autosus', '--avisar', titulo, texto], {
        cwd: this.pastaDownloads,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        windowsHide: true,
      });
      proc.on('error', () => ok(false));
      proc.on('close', (codigo) => ok(codigo === 0));
    });
  }

  /** Roda o downloader de verdade para a competência (um por vez) e volta na hora. */
  async verificar(aaaamm: string): Promise<{ execucao: number }> {
    if (this.emAndamento)
      throw new ConflictException(
        `o downloader já está verificando ${this.emAndamento.aaaamm}; aguarde terminar`,
      );
    if (!existsSync(this.python))
      throw new ConflictException(`Python não encontrado em ${this.python}`);
    const execucao = await this.prisma.execucaoDownload.create({ data: { aaaamm } });
    this.emAndamento = { aaaamm, execucao: execucao.id };
    const linhas: string[] = [];
    const guardar = (dados: Buffer) => {
      linhas.push(...dados.toString('utf-8').split(/\r?\n/).filter(Boolean));
      linhas.splice(0, Math.max(0, linhas.length - LINHAS_GUARDADAS));
    };
    const proc = spawn(this.python, ['-m', 'autosus', aaaamm], {
      cwd: this.pastaDownloads,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      windowsHide: true,
    });
    proc.stdout.on('data', guardar);
    proc.stderr.on('data', guardar);
    const terminar = async (codigo: number | null) => {
      try {
        await this.prisma.execucaoDownload.update({
          where: { id: execucao.id },
          data: { fim: new Date(), codigo, saida: linhas.join('\n') },
        });
        await this.importar(aaaamm);
      } finally {
        this.emAndamento = null;
      }
    };
    proc.on('error', (e) => {
      linhas.push(`erro ao iniciar o downloader: ${e.message}`);
      void terminar(-1);
    });
    proc.on('close', (codigo) => void terminar(codigo));
    this.log.log(`downloader iniciado para ${aaaamm} (execução ${execucao.id})`);
    return { execucao: execucao.id };
  }
}
