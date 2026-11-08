import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ScheduleModule } from '@nestjs/schedule';
import { AtualizacoesModule } from './atualizacoes/atualizacoes.module';
import { AuthModule } from './auth/auth.module';
import { CompetenciasModule } from './competencias/competencias.module';
import { PrismaModule } from './prisma/prisma.module';
import { ProcessamentoModule } from './processamento/processamento.module';
import { ServidorModule } from './servidor/servidor.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ScheduleModule.forRoot(),
    PrismaModule,
    AuthModule,
    CompetenciasModule,
    AtualizacoesModule,
    ServidorModule,
    ProcessamentoModule,
  ],
})
export class AppModule {}
