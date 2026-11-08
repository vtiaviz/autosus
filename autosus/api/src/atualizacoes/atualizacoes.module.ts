import { Module } from '@nestjs/common';
import { CompetenciasModule } from '../competencias/competencias.module';
import { AtualizacoesController } from './atualizacoes.controller';
import { AtualizacoesService } from './atualizacoes.service';

@Module({
  imports: [CompetenciasModule],
  controllers: [AtualizacoesController],
  providers: [AtualizacoesService],
})
export class AtualizacoesModule {}
