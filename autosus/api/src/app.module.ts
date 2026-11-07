import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ScheduleModule } from '@nestjs/schedule';
import { AtualizacoesModule } from './atualizacoes/atualizacoes.module';
import { AuthModule } from './auth/auth.module';
import { CompetenciasModule } from './competencias/competencias.module';
import { PrismaModule } from './prisma/prisma.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ScheduleModule.forRoot(),
    PrismaModule,
    AuthModule,
    CompetenciasModule,
    AtualizacoesModule,
  ],
})
export class AppModule {}
