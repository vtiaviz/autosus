import { Module } from '@nestjs/common';
import { AtualizacoesModule } from '../atualizacoes/atualizacoes.module';
import { ProcessamentoController } from './processamento.controller';
import { ProcessamentoService } from './processamento.service';

@Module({
  imports: [AtualizacoesModule],
  controllers: [ProcessamentoController],
  providers: [ProcessamentoService],
})
export class ProcessamentoModule {}
