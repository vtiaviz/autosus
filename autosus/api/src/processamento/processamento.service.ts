import { BadRequestException, ConflictException, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { Interval } from '@nestjs/schedule';
import { createHash } from 'node:crypto';
import { createReadStream, existsSync } from 'node:fs';
import { join } from 'node:path';
import { apresentacao, rotulo } from '../comum/competencia';
import { AtualizacoesService } from '../atualizacoes/atualizacoes.service';
import { PrismaService } from '../prisma/prisma.service';
import { ServidorService } from '../servidor/servidor.service';
import { ETAPAS, Etapa, Passo, situacaoPorSistema } from './sistemas';

const FINAIS = ['concluido', 'falhou', 'aguardando_decisao', 'cancelado', 'interrompido'];

export interface JobServidor {
  id: string;
  situacao: string;
  mensagem: string | null;
  passos: Passo[];
  passo_atual: number | null;
  progresso_agente?: string | null;
  conferencia: unknown;
  imagens?: string[];
  inicio: string | null;
  fim: string | null;
}

export type ModoEnvio = 'manual' | 'automatico';

function sha256(caminho: string): Promise<string> {
  return new Promise((ok, falha) => {
    const h = createHash('sha256');
    createReadStream(caminho)
      .on('data', (b) => h.update(b))
      .on('end', () => ok(h.digest('hex')))
      .on('error', falha);
  });
}

@Injectable()
export class ProcessamentoService {
  private readonly log = new Logger('Processamento');

  constructor(
    private readonly prisma: PrismaService,
    private readonly servidor: ServidorService,
    private readonly atualizacoes: AtualizacoesService,
  ) {}

  // ------------------------------------------------------------------ servidor

  async servidorSituacao() {
    try {
      const [vm, agente] = await Promise.all([
        this.servidor.json<Record<string, unknown>>('/vm'),
        this.servidor.json<Record<string, unknown>>('/agente'),
      ]);
      return { online: true, vm, agente };
    } catch (e) {
      return { online: false, erro: (e as Error).message };
    }
  }

  ligarServidor() {
    return this.servidor.json('/vm/ligar', { method: 'POST' });
  }

  // ------------------------------------------------------------------ arquivos

  /** Envia ao Server_SUS os arquivos e programas da competência que o downloader já baixou. */
  async enviarArquivos(aaaamm: string) {
    const dados = await this.atualizacoes.obter(aaaamm);
    const itens = [...dados.arquivos, ...dados.programas].filter(
      (i) => (i.situacao === 'baixado' || i.situacao === 'ja_existe') && i.arquivo,
    );
    if (!itens.length) throw new BadRequestException('nada baixado nesta competência ainda');
    const pastaComp = join(dados.pasta, `${aaaamm.slice(0, 4)}-${aaaamm.slice(4)}`);
    const resultado: { nome: string; arquivo: string; situacao: string; detalhe?: string }[] = [];
    for (const i of itens) {
      const caminho =
        i.tipo === 'programa'
          ? join(dados.pasta, 'programas', i.arquivo)
          : join(pastaComp, i.nome === 'BDSIA' ? 'SIA' : 'SIH', i.arquivo);
      if (!existsSync(caminho)) {
        resultado.push({ nome: i.nome, arquivo: i.arquivo, situacao: 'erro', detalhe: `não achei ${caminho}` });
        continue;
      }
      try {
        // o SHA-256 confere a transferência; ele é calculado agora, do arquivo como está no disco
        const sha = await sha256(caminho);
        const r = await this.servidor.enviarArquivo(aaaamm, caminho, sha);
        await this.prisma.itemAtualizacao.update({ where: { id: i.id }, data: { enviadoEm: new Date() } });
        resultado.push({
          nome: i.nome,
          arquivo: i.arquivo,
          situacao: r.situacao,
          detalhe: i.sha256 && i.sha256 !== sha ? 'o arquivo mudou depois do download (foi editado ou trocado)' : undefined,
        });
      } catch (e) {
        resultado.push({ nome: i.nome, arquivo: i.arquivo, situacao: 'erro', detalhe: (e as Error).message });
      }
    }
    return { aaaamm, itens: resultado };
  }

  // ------------------------------------------------------------------ jobs

  /**
   * Pede um processamento ao Server_SUS. No modo automático, o SIHD2 roda em modo manual (para nas AIHs
   * bloqueadas, isto é, com crítica) e o envio entra no mesmo job: só acontece se o SIHD2 terminar limpo.
   */
  async iniciar(aaaamm: string, etapas: string[], modoEnvio: ModoEnvio) {
    const invalidas = etapas.filter((e) => !(ETAPAS as readonly string[]).includes(e));
    if (!etapas.length || invalidas.length)
      throw new BadRequestException(`etapas inválidas: ${invalidas.join(', ') || '(nenhuma)'}`);
    if (etapas.includes('transmissor_enviar'))
      throw new BadRequestException('para transmitir use o botão Transmitir (POST /processamento/:aaaamm/transmitir)');
    const lista = [...etapas] as Etapa[];
    const opcoes: Record<string, unknown> = {};
    if (lista.includes('sihd')) {
      if (modoEnvio === 'automatico') {
        opcoes.sihd_manual = true;
        lista.push('transmissor_enviar');
        opcoes.confirmar_envio = true;
      }
    }
    return this.criarJob(aaaamm, lista, opcoes, lista.includes('transmissor_enviar') ? 'automatico' : 'manual');
  }

  /** Envio manual: o usuário confirmou na tela (digitando a competência). */
  async transmitir(aaaamm: string, confirmacao: string) {
    if (confirmacao !== rotulo(aaaamm))
      throw new BadRequestException(`para confirmar, digite a competência: ${rotulo(aaaamm)}`);
    const saidas = await this.servidor.json<{ arquivos: { nome: string }[] }>(`/competencias/${aaaamm}/saidas`);
    if (!saidas.arquivos.some((a) => a.nome.toUpperCase().endsWith(`${aaaamm}.DTS`)))
      throw new ConflictException('não há .DTS desta competência no Server_SUS: rode o SIHD2 antes');
    return this.criarJob(aaaamm, ['iniciar', 'transmissor_enviar'], { confirmar_envio: true }, 'manual');
  }

  private async criarJob(aaaamm: string, etapas: string[], opcoes: Record<string, unknown>, modoEnvio: ModoEnvio) {
    const ativo = await this.prisma.processamento.findFirst({ where: { situacao: { notIn: FINAIS } } });
    if (ativo)
      throw new ConflictException(
        `já há um processamento em andamento (${rotulo(ativo.aaaamm)}); cancele ou espere terminar`,
      );
    const job = await this.servidor.json<JobServidor>('/jobs', {
      method: 'POST',
      body: JSON.stringify({ competencia: aaaamm, etapas, ...opcoes }),
    });
    const p = await this.prisma.processamento.create({
      data: { aaaamm, jobId: job.id, etapas, modoEnvio, situacao: job.situacao, passos: job.passos as object[] },
    });
    this.log.log(`processamento ${p.id}: job ${job.id} (${rotulo(aaaamm)}: ${etapas.join(', ')})`);
    return p;
  }

  async cancelar(jobId: string) {
    const job = await this.servidor.json<JobServidor>(`/jobs/${encodeURIComponent(jobId)}/cancelar`, { method: 'POST' });
    await this.salvarJob(jobId, job);
    return job;
  }

  log_(jobId: string, desde: number) {
    return this.servidor.json<{ texto: string; proximo: number }>(
      `/jobs/${encodeURIComponent(jobId)}/log?desde=${Math.max(0, desde)}`,
    );
  }

  imagem(jobId: string, nome: string) {
    if (!/^[\w.-]+\.png$/.test(nome)) throw new NotFoundException();
    return this.servidor.binario(`/jobs/${encodeURIComponent(jobId)}/imagens/${encodeURIComponent(nome)}`);
  }

  // ------------------------------------------------------------------ acompanhamento

  /** A cada 15 s, traz do Server_SUS a situação dos jobs em andamento. */
  @Interval(15_000)
  async acompanhar() {
    const ativos = await this.prisma.processamento.findMany({ where: { situacao: { notIn: FINAIS } } });
    for (const p of ativos) {
      try {
        const job = await this.servidor.json<JobServidor>(`/jobs/${encodeURIComponent(p.jobId)}`);
        await this.salvarJob(p.jobId, job);
      } catch (e) {
        this.log.warn(`job ${p.jobId}: ${(e as Error).message}`);
      }
    }
  }

  private async salvarJob(jobId: string, job: JobServidor) {
    const p = await this.prisma.processamento.update({
      where: { jobId },
      data: {
        situacao: job.situacao,
        mensagem: job.mensagem,
        passos: job.passos as object[],
        conferencia: (job.conferencia ?? undefined) as object | undefined,
        imagens: job.imagens ?? [],
        inicio: job.inicio ? new Date(job.inicio) : null,
        fim: job.fim ? new Date(job.fim) : null,
      },
    });
    if (FINAIS.includes(p.situacao) && !p.avisadoEm) await this.avisarFim(p);
    return p;
  }

  /** Aviso no fim de cada processamento; no automático com crítica, explica que passou para o manual. */
  private async avisarFim(p: { id: number; aaaamm: string; etapas: string[]; modoEnvio: string; situacao: string; mensagem: string | null }) {
    const comp = rotulo(p.aaaamm);
    const enviar = p.etapas.includes('transmissor_enviar');
    let titulo: string;
    let texto: string;
    if (p.situacao === 'concluido') {
      titulo = enviar ? `AutoSUS: produção ${comp} transmitida` : `AutoSUS: processamento ${comp} concluído`;
      texto = enviar
        ? `O Transmissor enviou o .DTS da competência ${comp}. Confira o print do resultado em Processamento AIH.`
        : `Etapas concluídas: ${p.etapas.join(', ')}.`;
    } else if (p.modoEnvio === 'automatico' && p.situacao === 'aguardando_decisao') {
      titulo = `AutoSUS: ${comp} passou para envio manual`;
      texto =
        `O SIHD2 terminou com críticas (AIHs bloqueadas) na competência ${comp}, então nada foi transmitido. ` +
        `Resolva as AIHs bloqueadas e use o botão Transmitir em Processamento AIH.`;
    } else {
      titulo = `AutoSUS: processamento ${comp} ${p.situacao === 'cancelado' ? 'cancelado' : 'parou'}`;
      texto = `${p.mensagem ?? p.situacao}. Veja o log em Processamento AIH.`;
    }
    const ok = await this.atualizacoes.avisar(titulo, texto);
    await this.prisma.processamento.update({ where: { id: p.id }, data: { avisadoEm: new Date() } });
    this.log.log(`aviso ${ok ? 'enviado' : 'falhou'}: ${titulo}`);
  }

  // ------------------------------------------------------------------ consulta

  async obter(aaaamm: string) {
    const processamentos = await this.prisma.processamento.findMany({
      where: { aaaamm },
      orderBy: { criadoEm: 'desc' },
      take: 20,
    });
    const jobs = processamentos.map((p) => ({ ...p, passos: p.passos as unknown as Passo[] }));
    let progresso: string | null = null;
    const ativo = jobs.find((j) => !FINAIS.includes(j.situacao));
    if (ativo) {
      try {
        const job = await this.servidor.json<JobServidor>(`/jobs/${encodeURIComponent(ativo.jobId)}`);
        await this.salvarJob(ativo.jobId, job);
        Object.assign(ativo, { situacao: job.situacao, passos: job.passos, mensagem: job.mensagem });
        progresso = job.progresso_agente ?? null;
      } catch {
        /* o Server_SUS pode estar fora do ar; mostra o que o banco sabe */
      }
    }
    let entrada: unknown = null;
    let saidas: unknown = null;
    try {
      [entrada, saidas] = await Promise.all([
        this.servidor.json(`/competencias/${aaaamm}/arquivos`),
        this.servidor.json(`/competencias/${aaaamm}/saidas`),
      ]);
    } catch {
      /* idem */
    }
    return {
      aaaamm,
      apresentacao: apresentacao(aaaamm),
      sistemas: situacaoPorSistema(jobs),
      processamentos: jobs,
      progresso,
      entrada,
      saidas,
    };
  }

  /** Só a situação de cada sistema, para o Dashboard. */
  async resumo(aaaamm: string) {
    const jobs = await this.prisma.processamento.findMany({ where: { aaaamm } });
    return situacaoPorSistema(jobs.map((p) => ({ ...p, passos: p.passos as unknown as Passo[] })));
  }
}
