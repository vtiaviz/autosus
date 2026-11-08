import { BadRequestException, Controller, Get, Param, Post } from '@nestjs/common';
import { PADRAO_COMPETENCIA } from '../comum/competencia';
import { CompetenciasService } from './competencias.service';

@Controller('competencias')
export class CompetenciasController {
  constructor(private readonly competencias: CompetenciasService) {}

  @Get()
  listar() {
    return this.competencias.listar();
  }

  @Get(':aaaamm')
  obter(@Param('aaaamm') aaaamm: string) {
    if (!PADRAO_COMPETENCIA.test(aaaamm)) throw new BadRequestException('use AAAAMM');
    return this.competencias.obter(aaaamm);
  }

  /** Lê de novo o cronograma do wiki do CNES. */
  @Post('sincronizar')
  sincronizar() {
    return this.competencias.sincronizar();
  }
}
