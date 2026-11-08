import { Module } from '@nestjs/common';
import { CompetenciasController } from './competencias.controller';
import { CompetenciasService } from './competencias.service';

@Module({
  controllers: [CompetenciasController],
  providers: [CompetenciasService],
  exports: [CompetenciasService],
})
export class CompetenciasModule {}
