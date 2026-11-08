import { BadRequestException, Controller, Get, HttpCode, Param, Post } from '@nestjs/common';
import { PADRAO_COMPETENCIA } from '../comum/competencia';
import { AtualizacoesService } from './atualizacoes.service';

function validar(aaaamm: string): string {
  if (!PADRAO_COMPETENCIA.test(aaaamm)) throw new BadRequestException('use AAAAMM');
  return aaaamm;
}

@Controller('atualizacoes')
export class AtualizacoesController {
  constructor(private readonly atualizacoes: AtualizacoesService) {}

  /** Arquivos e programas da competência na última verificação, e a última execução do downloader. */
  @Get(':aaaamm')
  obter(@Param('aaaamm') aaaamm: string) {
    return this.atualizacoes.obter(validar(aaaamm));
  }

  /** Verifica e baixa o que falta (roda o downloader). Acompanhe com GET /atualizacoes/:aaaamm. */
  @Post(':aaaamm/verificar')
  @HttpCode(202)
  verificar(@Param('aaaamm') aaaamm: string) {
    return this.atualizacoes.verificar(validar(aaaamm));
  }
}
