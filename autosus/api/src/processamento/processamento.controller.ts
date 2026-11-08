import { BadRequestException, Body, Controller, Get, HttpCode, Param, Post, Query, Res } from '@nestjs/common';
import { ArrayNotEmpty, IsArray, IsIn, IsString, Matches } from 'class-validator';
import type { Response } from 'express';
import { PADRAO_COMPETENCIA } from '../comum/competencia';
import { ProcessamentoService } from './processamento.service';
import { ETAPAS } from './sistemas';

class NovoProcessamento {
  @IsArray()
  @ArrayNotEmpty()
  @IsIn(ETAPAS as unknown as string[], { each: true })
  etapas!: string[];

  @IsIn(['manual', 'automatico'])
  modoEnvio: 'manual' | 'automatico' = 'manual';
}

class Liberar {
  /** AIHs aprovadas; vazio = não libera nenhuma e só continua o SIHD2 */
  @IsArray()
  @Matches(/^\d{12}-\d$/, { each: true, message: 'AIH no formato 152610159490-8' })
  aihs!: string[];
}

class Transmitir {
  @IsString()
  confirmacao!: string;
}

function competencia(aaaamm: string): string {
  if (!PADRAO_COMPETENCIA.test(aaaamm)) throw new BadRequestException('use AAAAMM');
  return aaaamm;
}

@Controller('processamento')
export class ProcessamentoController {
  constructor(private readonly processamento: ProcessamentoService) {}

  @Get('servidor')
  servidor() {
    return this.processamento.servidorSituacao();
  }

  @Post('servidor/ligar')
  @HttpCode(200)
  ligar() {
    return this.processamento.ligarServidor();
  }

  @Get('jobs/:jobId/log')
  log(@Param('jobId') jobId: string, @Query('desde') desde = '0') {
    return this.processamento.log_(jobId, Number(desde) || 0);
  }

  @Get('jobs/:jobId/imagens/:nome')
  async imagem(@Param('jobId') jobId: string, @Param('nome') nome: string, @Res() res: Response) {
    const { tipo, dados } = await this.processamento.imagem(jobId, nome);
    res.type(tipo).send(dados);
  }

  @Post('jobs/:jobId/cancelar')
  @HttpCode(200)
  cancelar(@Param('jobId') jobId: string) {
    return this.processamento.cancelar(jobId);
  }

  @Get(':aaaamm')
  obter(@Param('aaaamm') aaaamm: string) {
    return this.processamento.obter(competencia(aaaamm));
  }

  @Get(':aaaamm/resumo')
  resumo(@Param('aaaamm') aaaamm: string) {
    return this.processamento.resumo(competencia(aaaamm));
  }

  /** Envia ao Server_SUS os arquivos e programas já baixados da competência. */
  @Post(':aaaamm/arquivos')
  @HttpCode(200)
  enviarArquivos(@Param('aaaamm') aaaamm: string) {
    return this.processamento.enviarArquivos(competencia(aaaamm));
  }

  @Post(':aaaamm')
  iniciar(@Param('aaaamm') aaaamm: string, @Body() pedido: NovoProcessamento) {
    return this.processamento.iniciar(competencia(aaaamm), pedido.etapas, pedido.modoEnvio);
  }

  /** Decisão das AIHs bloqueadas no SIHD2: libera as aprovadas e continua (não transmite). */
  @Post(':aaaamm/liberar')
  liberar(@Param('aaaamm') aaaamm: string, @Body() pedido: Liberar) {
    return this.processamento.liberar(competencia(aaaamm), pedido.aihs);
  }

  /** Envio real ao DATASUS: exige digitar a competência (MM/AAAA) como confirmação. */
  @Post(':aaaamm/transmitir')
  transmitir(@Param('aaaamm') aaaamm: string, @Body() pedido: Transmitir) {
    return this.processamento.transmitir(competencia(aaaamm), pedido.confirmacao);
  }
}
