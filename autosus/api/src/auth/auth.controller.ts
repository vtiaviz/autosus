import { Body, Controller, Get, HttpCode, Post, Req, Res } from '@nestjs/common';
import { IsEmail, IsString, MinLength } from 'class-validator';
import type { Request, Response } from 'express';
import { AuthService } from './auth.service';
import { COOKIE, type Sessao } from './jwt.guard';
import { Publico } from './publico.decorator';

class Login {
  @IsEmail({}, { message: 'informe um e-mail válido' })
  email!: string;

  @IsString()
  @MinLength(1, { message: 'informe a senha' })
  senha!: string;
}

const OITO_HORAS = 8 * 3600 * 1000;

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}

  @Publico()
  @Post('entrar')
  @HttpCode(200)
  async entrar(@Body() dados: Login, @Res({ passthrough: true }) res: Response) {
    const { token, usuario } = await this.auth.entrar(dados.email, dados.senha);
    res.cookie(COOKIE, token, {
      httpOnly: true,
      sameSite: 'lax',
      maxAge: OITO_HORAS,
      path: '/',
    });
    return { usuario, token };
  }

  @Publico()
  @Post('sair')
  @HttpCode(204)
  sair(@Res({ passthrough: true }) res: Response) {
    res.clearCookie(COOKIE, { path: '/' });
  }

  @Get('eu')
  eu(@Req() req: Request & { sessao: Sessao }) {
    const { email, nome, perfil } = req.sessao;
    return { email, nome, perfil };
  }
}
