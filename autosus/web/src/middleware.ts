import { NextResponse, type NextRequest } from 'next/server';

// Sem o cookie da sessão, qualquer página vai para o login (a API confere o token de verdade).
export function middleware(req: NextRequest) {
  if (!req.cookies.get('autosus_sessao')) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.search = '';
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!login|api|_next|hsus|favicon.ico).*)'],
};
