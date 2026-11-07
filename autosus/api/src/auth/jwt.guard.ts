import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { JwtService } from '@nestjs/jwt';
import type { Request } from 'express';
import { PUBLICO } from './publico.decorator';

export const COOKIE = 'autosus_sessao';

export interface Sessao {
  sub: number;
  email: string;
  nome: string;
  perfil: string;
}

/** Lê o token do cookie da sessão (navegador) ou do cabeçalho Authorization: Bearer. */
export function tokenDaRequisicao(req: Request): string | undefined {
  const auth = req.headers.authorization;
  if (auth?.startsWith('Bearer ')) return auth.slice(7);
  for (const parte of (req.headers.cookie ?? '').split(';')) {
    const [nome, ...valor] = parte.trim().split('=');
    if (nome === COOKIE) return decodeURIComponent(valor.join('='));
  }
  return undefined;
}

@Injectable()
export class JwtGuard implements CanActivate {
  constructor(
    private readonly jwt: JwtService,
    private readonly reflector: Reflector,
  ) {}

  async canActivate(ctx: ExecutionContext): Promise<boolean> {
    const publico = this.reflector.getAllAndOverride<boolean>(PUBLICO, [
      ctx.getHandler(),
      ctx.getClass(),
    ]);
    if (publico) return true;
    const req = ctx.switchToHttp().getRequest<Request & { sessao?: Sessao }>();
    const token = tokenDaRequisicao(req);
    if (!token) throw new UnauthorizedException('faça login');
    try {
      req.sessao = await this.jwt.verifyAsync<Sessao>(token);
    } catch {
      throw new UnauthorizedException('sessão expirada; faça login de novo');
    }
    return true;
  }
}
