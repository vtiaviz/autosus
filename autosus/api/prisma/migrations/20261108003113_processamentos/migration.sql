-- CreateTable
CREATE TABLE "processamentos" (
    "id" SERIAL NOT NULL,
    "aaaamm" TEXT NOT NULL,
    "job_id" TEXT NOT NULL,
    "etapas" TEXT[],
    "modo_envio" TEXT NOT NULL DEFAULT 'manual',
    "situacao" TEXT NOT NULL DEFAULT 'na_fila',
    "mensagem" TEXT,
    "passos" JSONB NOT NULL DEFAULT '[]',
    "conferencia" JSONB,
    "imagens" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "inicio" TIMESTAMP(3),
    "fim" TIMESTAMP(3),
    "avisado_em" TIMESTAMP(3),

    CONSTRAINT "processamentos_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "processamentos_job_id_key" ON "processamentos"("job_id");

-- CreateIndex
CREATE INDEX "processamentos_aaaamm_idx" ON "processamentos"("aaaamm");
