-- Comandos para o banco de dados que usei no supabase para criar o banco de dados

CREATE TYPE tipo_usuario_enum AS ENUM ('aluno', 'professor');

CREATE TABLE usuarios (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    tipo_usuario tipo_usuario_enum NOT NULL,
    id_turma INT,
    data_cadastro TIMESTAMP DEFAULT NOW()
);

CREATE TABLE turmas (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    codigo TEXT UNIQUE NOT NULL,
    id_professor INT NOT NULL REFERENCES usuarios(id)
);

ALTER TABLE usuarios
ADD CONSTRAINT fk_turma
FOREIGN KEY (id_turma)
REFERENCES turmas(id);

CREATE TABLE exercicios (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pergunta TEXT NOT NULL,
    resposta_correta TEXT NOT NULL,
    categoria TEXT NOT NULL,
    nivel TEXT NOT NULL,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tentativas (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_aluno INT NOT NULL REFERENCES usuarios(id),
    id_exercicio INT NOT NULL REFERENCES exercicios(id),
    resposta_usuario TEXT NOT NULL,
    correta BOOLEAN NOT NULL,
    tipo_erro TEXT,
    numero_tentativa INTEGER DEFAULT 1,
    criado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE dicas (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria TEXT NOT NULL,
    tipo_erro TEXT NOT NULL,
    dica TEXT NOT NULL
);

CREATE TABLE videos (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria TEXT NOT NULL,
    titulo TEXT NOT NULL,
    url TEXT NOT NULL
);