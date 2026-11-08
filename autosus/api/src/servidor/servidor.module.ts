import { Global, Module } from '@nestjs/common';
import { ServidorService } from './servidor.service';

@Global()
@Module({
  providers: [ServidorService],
  exports: [ServidorService],
})
export class ServidorModule {}
