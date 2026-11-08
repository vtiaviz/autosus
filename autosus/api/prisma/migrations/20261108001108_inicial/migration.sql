-- CreateTable
CREATE TABLE "usuarios" (
    "id" SERIAL NOT NULL,
    "email" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "senha_hash" TEXT NOT NULL,
    "perfil" TEXT NOT NULL DEFAULT 'administrador',
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "usuarios_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "competencias" (
    "aaaamm" TEXT NOT NULL,
    "apresentacao" TEXT NOT NULL,
    "abertura" DATE,
    "fechamento" DATE,
    "datas" JSONB NOT NULL DEFAULT '[]',
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "competencias_pkey" PRIMARY KEY ("aaaamm")
);

-- CreateTable
CREATE TABLE "itens_atualizacao" (
    "id" SERIAL NOT NULL,
    "aaaamm" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "tipo" TEXT NOT NULL,
    "situacao" TEXT NOT NULL,
    "arquivo" TEXT NOT NULL DEFAULT '',
    "versao" TEXT NOT NULL DEFAULT '',
    "detalhe" TEXT NOT NULL DEFAULT '',
    "tamanho" BIGINT NOT NULL DEFAULT 0,
    "sha256" TEXT,
    "revisao_nova" BOOLEAN NOT NULL DEFAULT false,
    "verificado_em" TIMESTAMP(3) NOT NULL,
    "enviado_em" TIMESTAMP(3),

    CONSTRAINT "itens_atualizacao_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "execucoes_download" (
    "id" SERIAL NOT NULL,
    "aaaamm" TEXT NOT NULL,
    "inicio" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fim" TIMESTAMP(3),
    "codigo" INTEGER,
    "saida" TEXT NOT NULL DEFAULT '',

    CONSTRAINT "execucoes_download_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "usuarios_email_key" ON "usuarios"("email");

-- CreateIndex
CREATE UNIQUE INDEX "itens_atualizacao_aaaamm_nome_key" ON "itens_atualizacao"("aaaamm", "nome");

-- AddForeignKey
ALTER TABLE "itens_atualizacao" ADD CONSTRAINT "itens_atualizacao_aaaamm_fkey" FOREIGN KEY ("aaaamm") REFERENCES "competencias"("aaaamm") ON DELETE RESTRICT ON UPDATE CASCADE;
