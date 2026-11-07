import { SetMetadata } from '@nestjs/common';

export const PUBLICO = 'rota-publica';

/** Rota que não exige login (por padrão todas exigem). */
export const Publico = () => SetMetadata(PUBLICO, true);
