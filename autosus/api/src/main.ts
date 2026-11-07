import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  // o Next.js (autosus/web) repassa /api/* para cá, na mesma máquina
  app.setGlobalPrefix('api');
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
  const porta = Number(process.env.PORT ?? 3001);
  await app.listen(porta, '127.0.0.1');
}
void bootstrap();
