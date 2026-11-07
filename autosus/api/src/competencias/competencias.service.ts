import { Injectable, Logger, NotFoundException, OnApplicationBootstrap } from '@nestjs/common';
import { Cron } from '@nestjs/schedule';
import { apresentacao } from '../comum/competencia';
import { PrismaService } from '../prisma/prisma.service';
import { lerCronograma, situacao, URL_CRONOGRAMA } from './cronograma';

@Injectable()
export class CompetenciasService implements OnApplicationBootstrap {
  private readonly log = new Logger('Competencias');

  constructor(private readonly prisma: PrismaService) {}

  /** Na primeira subida (banco sem datas) já lê o cronograma. */
  async onApplicationBootstrap() {
    if ((await this.prisma.competencia.count({ where: { abertura: { not: null } } })) === 0) {
      await this.sincronizar().catch((e: Error) =>
        this.log.warn(`cronograma não lido: ${e.message}`),
      );
    }
  }

  /** Toda segunda-feira às 7h: o Ministério ajusta datas durante o ano. */
  @Cron('0 7 * * 1')
  async sincronizarAgendado() {
    await this.sincronizar().catch((e: Error) =>
      this.log.warn(`cronograma não lido: ${e.message}`),
    );
  }

  async sincronizar(html?: string): Promise<{ competencias: number }> {
    if (html === undefined) {
      const resp = await fetch(URL_CRONOGRAMA, { signal: AbortSignal.timeout(60_000) });
      if (!resp.ok) throw new Error(`wiki do CNES respondeu ${resp.status}`);
      html = await resp.text();
    }
    const linhas = lerCronograma(html);
    if (linhas.length === 0) throw new Error('a página do cronograma não tem a tabela esperada');
    for (const l of linhas) {
      const dados = {
        apresentacao: apresentacao(l.aaaamm),
        abertura: l.abertura ? new Date(l.abertura) : null,
        fechamento: l.fechamento ? new Date(l.fechamento) : null,
        datas: l.datas as object[],
      };
      await this.prisma.competencia.upsert({
        where: { aaaamm: l.aaaamm },
        create: { aaaamm: l.aaaamm, ...dados },
        update: dados,
      });
    }
    this.log.log(`cronograma: ${linhas.length} competências atualizadas`);
    return { competencias: linhas.length };
  }

  /** Garante a linha da competência (para itens de competências fora do cronograma lido). */
  async garantir(aaaamm: string) {
    return this.prisma.competencia.upsert({
      where: { aaaamm },
      create: { aaaamm, apresentacao: apresentacao(aaaamm) },
      update: {},
    });
  }

  async listar(hoje = new Date()) {
    const lista = await this.prisma.competencia.findMany({
      orderBy: { aaaamm: 'desc' },
      include: { itens: { select: { tipo: true, situacao: true } } },
    });
    return lista.map((c) => this.resumo(c, hoje));
  }

  async obter(aaaamm: string, hoje = new Date()) {
    const c = await this.prisma.competencia.findUnique({
      where: { aaaamm },
      include: { itens: { select: { tipo: true, situacao: true } } },
    });
    if (!c) throw new NotFoundException('competência não encontrada');
    return this.resumo(c, hoje);
  }

  private resumo(
    c: {
      aaaamm: string;
      apresentacao: string;
      abertura: Date | null;
      fechamento: Date | null;
      datas: unknown;
      itens: { tipo: string; situacao: string }[];
    },
    hoje: Date,
  ) {
    const conta = (tipo: string) => {
      const itens = c.itens.filter((i) => i.tipo === tipo);
      const ok = itens.filter((i) => i.situacao === 'baixado' || i.situacao === 'ja_existe').length;
      return { baixados: ok, pendentes: itens.length - ok };
    };
    return {
      aaaamm: c.aaaamm,
      apresentacao: c.apresentacao,
      abertura: c.abertura?.toISOString().slice(0, 10) ?? null,
      fechamento: c.fechamento?.toISOString().slice(0, 10) ?? null,
      datas: c.datas,
      situacao: situacao(c.abertura, c.fechamento, hoje),
      arquivos: conta('arquivo'),
      programas: conta('programa'),
    };
  }
}
