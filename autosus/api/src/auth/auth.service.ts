import {
  Injectable,
  Logger,
  OnModuleInit,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';
import { PrismaService } from '../prisma/prisma.service';
import type { Sessao } from './jwt.guard';

@Injectable()
export class AuthService implements OnModuleInit {
  private readonly log = new Logger('Auth');

  constructor(
    private readonly prisma: PrismaService,
    private readonly jwt: JwtService,
    private readonly config: ConfigService,
  ) {}

  /** Sem nenhum usuário no banco, cria o administrador com ADMIN_EMAIL / ADMIN_SENHA do .env. */
  async onModuleInit() {
    if ((await this.prisma.usuario.count()) > 0) return;
    const email = this.config.get<string>('ADMIN_EMAIL');
    const senha = this.config.get<string>('ADMIN_SENHA');
    if (!email || !senha) {
      this.log.warn(
        'Nenhum usuário cadastrado: preencha ADMIN_EMAIL e ADMIN_SENHA no .env',
      );
      return;
    }
    await this.prisma.usuario.create({
      data: {
        email: email.toLowerCase(),
        nome: this.config.get<string>('ADMIN_NOME') ?? 'Administrador',
        senhaHash: await bcrypt.hash(senha, 12),
        perfil: 'administrador',
      },
    });
    this.log.log(`Administrador criado: ${email}`);
  }

  async entrar(
    email: string,
    senha: string,
  ): Promise<{ token: string; usuario: Omit<Sessao, 'sub'> }> {
    const usuario = await this.prisma.usuario.findUnique({
      where: { email: email.toLowerCase() },
    });
    const ok =
      usuario?.ativo && (await bcrypt.compare(senha, usuario.senhaHash));
    if (!usuario || !ok) throw new UnauthorizedException('e-mail ou senha incorretos');
    const sessao: Sessao = {
      sub: usuario.id,
      email: usuario.email,
      nome: usuario.nome,
      perfil: usuario.perfil,
    };
    return {
      token: await this.jwt.signAsync(sessao),
      usuario: { email: usuario.email, nome: usuario.nome, perfil: usuario.perfil },
    };
  }
}
