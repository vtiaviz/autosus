// @nestjs/schedule 12 é só ESM e o Jest (CommonJS) não carrega: nos testes os decoradores não fazem nada.
const decorador = () => () => undefined;
export const Cron = decorador;
export const Interval = decorador;
export const Timeout = decorador;
export class SchedulerRegistry {}
export const ScheduleModule = { forRoot: () => ({ module: class {} }) };
