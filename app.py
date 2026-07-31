from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from flask_cors import CORS
from flasgger import Swagger
from auth import auth_bp
import random
import string
from werkzeug.security import generate_password_hash
from gemini_client import client

from supabase_client import supabase

import os

load_dotenv()

app = Flask(__name__)

app.config['SWAGGER'] = {
    'openapi': '3.0.3'
}

swagger = Swagger(app, template_file='openapi.yaml')

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

CORS(app, origins="*")

app.register_blueprint(auth_bp)

# ==========================
# ROTA PRINCIPAL
# ==========================

@app.route("/", methods=["GET"])
def root():

    return jsonify({
        "api": "Fracta",
        "version": "1.0",
        "author": "Elektron"
    }), 200

# ==========================
# LISTAR USUÁRIOS
# ==========================

@app.route("/usuarios", methods=["GET"])
def get_usuarios():

    resposta = supabase.table("usuarios").select("*").execute()

    return jsonify(resposta.data), 200

# ==========================
# CADASTRAR USUÁRIO
# ==========================

@app.route("/usuarios", methods=["POST"])
def post_usuario():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    nome = dados.get("nome")
    email = dados.get("email")
    senha = dados.get("senha")
    tipo_usuario = dados.get("tipo_usuario")

    if not nome or not email or not senha or not tipo_usuario:
        return jsonify({
            "erro": "Todos os campos são obrigatórios"
        }), 400

    # Validação do tipo de usuário
    if tipo_usuario not in ["aluno", "professor"]:
        return jsonify({
            "erro": "Tipo de usuário inválido"
        }), 400

    senha_hash = generate_password_hash(senha)

    try:

        usuario = supabase.table("usuarios") \
            .select("*") \
            .eq("email", email) \
            .execute()

        if usuario.data:
            return jsonify({
                "erro": "Email já cadastrado"
            }), 400

        supabase.table("usuarios").insert({
            "nome": nome,
            "email": email,
            "senha": senha_hash,
            "tipo_usuario": tipo_usuario
        }).execute()

        return jsonify({
            "mensagem": "Usuário cadastrado com sucesso"
        }), 201

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500
    
# ==========================
# DELETAR USUÁRIO
# ==========================

@app.route("/usuarios/<int:id>", methods=["DELETE"])
def delete_usuario(id):

    try:

        usuario = supabase.table("usuarios") \
            .select("*") \
            .eq("id", id) \
            .execute()

        if not usuario.data:
            return jsonify({
                "erro": "Usuário não encontrado"
            }), 404

        supabase.table("usuarios") \
            .delete() \
            .eq("id", id) \
            .execute()

        return jsonify({
            "mensagem": "Usuário removido com sucesso"
        }), 200

    except:
        return jsonify({
            "erro": "Falha ao remover usuário"
        }), 500

# ==========================
# CADASTRAR EXERCÍCIO
# ==========================

@app.route("/exercicios", methods=["POST"])
def post_exercicio():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    try:

        supabase.table("exercicios").insert({
            "pergunta": dados["pergunta"],
            "resposta_correta": dados["resposta_correta"],
            "categoria": dados["categoria"],
            "nivel": dados["nivel"]
        }).execute()

        return jsonify({
            "mensagem": "Exercício cadastrado com sucesso"
        }), 201

    except:
        return jsonify({
            "erro": "Falha ao cadastrar exercício"
        }), 500
    
# ==========================
# BUSCAR EXERCÍCIOS 
# ==========================

@app.route("/exercicios", methods=["GET"])
def get_exercicios():

    try:

        resposta = supabase.table("exercicios") \
            .select("*") \
            .execute()

        return jsonify(resposta.data), 200

    except:
        return jsonify({
            "erro": "Falha ao buscar exercícios"
        }), 500

# ==========================
# TENTATIVAS QUESTÕES
# ==========================

@app.route("/tentativas", methods=["POST"])
def post_tentativa():

    dados = request.get_json()

    id_aluno = dados.get("id_aluno")
    id_exercicio = dados.get("id_exercicio")
    resposta_usuario = dados.get("resposta_usuario")

    if not id_aluno or not id_exercicio or not resposta_usuario:
        return jsonify({
            "erro": "Dados obrigatórios"
        }), 400

    try:

        exercicio = supabase.table("exercicios") \
            .select("*") \
            .eq("id", id_exercicio) \
            .execute()

        if not exercicio.data:
            return jsonify({
                "erro": "Exercício não encontrado"
            }), 404

        exercicio = exercicio.data[0]

        correta = (
            resposta_usuario.strip()
            ==
            exercicio["resposta_correta"].strip()
        )

        tipo_erro = None

        if not correta:
            tipo_erro = "Resposta incorreta"

        supabase.table("tentativas").insert({
            "id_aluno": id_aluno,
            "id_exercicio": id_exercicio,
            "resposta_usuario": resposta_usuario,
            "correta": correta,
            "tipo_erro": tipo_erro
        }).execute()

        return jsonify({
            "correta": correta,
            "tipo_erro": tipo_erro
        }), 201

    except:
        return jsonify({
            "erro": "Falha ao registrar tentativa"
        }), 500

# ==========================
# LISTAR TENTATIVAS DO ALUNO
# ==========================

@app.route("/tentativas/<int:id_aluno>", methods=["GET"])
def get_tentativas_aluno(id_aluno):
    try:
        resposta = supabase.table("tentativas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()
        return jsonify(resposta.data), 200
    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# CRIAR TURMAS
# ==========================

@app.route("/turmas", methods=["POST"])
def post_turma():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    nome = dados.get("nome")
    id_professor = dados.get("id_professor")
    id_trilha = dados.get("id_trilha")

    if not nome or not id_professor:
        return jsonify({
            "erro": "Nome da turma e id_professor são obrigatórios"
        }), 400

    if not nome or not id_professor or not id_trilha:
        return jsonify({
            "erro": "Nome, professor e trilha são obrigatórios"
        }), 400

    try:

        # Gera código aleatório de 6 caracteres
        codigo = ''.join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )

        supabase.table("turmas").insert({
            "nome": nome,
            "codigo": codigo,
            "id_professor": id_professor,
            "id_trilha": id_trilha
        }).execute()

        return jsonify({
            "mensagem": "Turma criada com sucesso",
            "codigo": codigo
        }), 201

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# LISTAR TURMAS
# ==========================
@app.route("/turmas", methods=["GET"])
def get_turmas():
    try:
        resposta = supabase.table("turmas") \
            .select("*") \
            .execute()
        return jsonify(resposta.data), 200
    except:
        return jsonify({
            "erro": "Falha ao buscar turmas"
        }), 500

# ==========================
# LISTAR TRILHAS
# ==========================
@app.route("/trilhas", methods=["GET"])
def get_trilhas():
    try:
        resposta = supabase.table("trilhas") \
            .select("*") \
            .execute()
        return jsonify(resposta.data), 200

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# CAPÍTULOS DA TRILHA
# ==========================
@app.route("/trilhas/<int:id_trilha>/capitulos", methods=["GET"])
def get_capitulos(id_trilha):
    try:
        resposta = supabase.table("capitulos") \
            .select("*") \
            .eq("id_trilha", id_trilha) \
            .order("ordem") \
            .execute()
        return jsonify(resposta.data), 200

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# CAPÍTULO ATUAL DO ALUNO
# ==========================
@app.route("/progresso/<int:id_aluno>", methods=["GET"])
def progresso_aluno(id_aluno):
    try:
        resposta = supabase.table("progresso_aluno") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()
        return jsonify(resposta.data), 200

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# CONCLUIR CAPÍTULO
# ==========================
@app.route("/progresso", methods=["POST"])
def concluir_capitulo():
    dados = request.get_json()
    try:
        supabase.table("progresso_aluno").insert({
            "id_aluno": dados["id_aluno"],
            "id_capitulo": dados["id_capitulo"],
            "concluido": True
        }).execute()
        return jsonify({
            "mensagem": "Capítulo concluído."
        }), 201

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# ENTRAR EM TURMA
# ==========================
@app.route("/entrar-turma", methods=["POST"])
def entrar_turma():
    dados = request.get_json()
    id_aluno = dados.get("id_aluno")
    codigo = dados.get("codigo")

    if not id_aluno or not codigo:
        return jsonify({
            "erro": "Dados obrigatórios"
        }), 400

    try:
        turma = supabase.table("turmas") \
            .select("*") \
            .eq("codigo", codigo) \
            .execute()

        if not turma.data:
            return jsonify({
                "erro": "Código inválido"
            }), 404

        turma = turma.data[0]

        supabase.table("usuarios") \
            .update({
                "id_turma": turma["id"]
            }) \
            .eq("id", id_aluno) \
            .execute()

        return jsonify({
            "mensagem": "Aluno entrou na turma",
            "turma": turma["nome"]
        }), 200

    except:
        return jsonify({
            "erro": "Falha ao entrar na turma"
        }), 500
    
# ==========================
# DASHBOARD DO ALUNO
# ==========================
@app.route("/dashboard/<int:id_aluno>", methods=["GET"])
def dashboard_aluno(id_aluno):
    try:
        resposta = supabase.table("tentativas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()

        tentativas = resposta.data
        total_tentativas = len(tentativas)
        acertos = sum(
            1 for tentativa in tentativas
            if tentativa["correta"] == True
        )

        erros = total_tentativas - acertos
        percentual_acerto = 0

        if total_tentativas > 0:
            percentual_acerto = round(
                (acertos / total_tentativas) * 100,
                2
            )

        return jsonify({
            "id_aluno": id_aluno,
            "total_tentativas": total_tentativas,
            "acertos": acertos,
            "erros": erros,
            "percentual_acerto": percentual_acerto
        }), 200

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# ANÁLISE DO ALUNO
# ==========================
@app.route("/analise-aluno/<int:id_aluno>", methods=["GET"])
def analise_aluno(id_aluno):
    try:
        # Busca todas as tentativas do aluno
        resposta = supabase.table("tentativas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()

        tentativas = resposta.data

        if not tentativas:
            return jsonify({
                "erro": "Aluno sem tentativas registradas"
            }), 404

        total_tentativas = len(tentativas)

        acertos = sum(
            1 for tentativa in tentativas
            if tentativa["correta"]
        )

        erros = total_tentativas - acertos

        percentual_acerto = round(
            (acertos / total_tentativas) * 100,
            2
        )

        # Contadores por categoria
        categorias = {}

        for tentativa in tentativas:
            exercicio = supabase.table("exercicios") \
                .select("categoria") \
                .eq("id", tentativa["id_exercicio"]) \
                .execute()
            if not exercicio.data:
                continue

            categoria = exercicio.data[0]["categoria"]

            if categoria not in categorias:
                categorias[categoria] = {
                    "acertos": 0,
                    "erros": 0
                }

            if tentativa["correta"]:
                categorias[categoria]["acertos"] += 1
            else:
                categorias[categoria]["erros"] += 1

        # Feedback simples
        if percentual_acerto >= 80:
            feedback = "Excelente desempenho nas atividades de frações."
        elif percentual_acerto >= 60:
            feedback = "Bom desempenho, mas ainda existem conteúdos para reforçar."
        else:
            feedback = "Recomenda-se revisar os conceitos básicos de frações e praticar mais exercícios."

        return jsonify({
            "id_aluno": id_aluno,
            "total_tentativas": total_tentativas,
            "acertos": acertos,
            "erros": erros,
            "percentual_acerto": percentual_acerto,
            "categorias": categorias,
            "feedback": feedback
        }), 200

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# DEVOLUTIVA COM IA
# ==========================

@app.route("/devolutiva-ia/<int:id_aluno>", methods=["GET"])
def devolutiva_ia(id_aluno):
    try:
        resposta = supabase.table("tentativas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()
        tentativas = resposta.data
        if not tentativas:
            return jsonify({
                "erro": "Aluno sem tentativas"
            }), 404
        total = len(tentativas)
        acertos = sum(
            1 for t in tentativas
            if t["correta"]
        )
        erros = total - acertos
        tipos_erro = [
        t["tipo_erro"]
        for t in tentativas
        if t["tipo_erro"]
        ]
        percentual = round(
            (acertos / total) * 100,
            2
        )
        prompt = f"""
        Você é um professor de matemática especializado no ensino de frações.

        Analise o desempenho deste aluno:

        Total de tentativas: {total}
        Acertos: {acertos}
        Erros: {erros}
        Percentual de acerto: {percentual}%

        Principais erros encontrados:
        {tipos_erro}

        Crie uma devolutiva pedagógica:

        - Utilize linguagem amigável e motivadora.
        - Destaque os pontos positivos do aluno.
        - Comente possíveis dificuldades observadas.
        - Sugira o que ele deve revisar ou praticar.
        - Responda em no máximo 5 linhas.
        - Não utilize markdown, listas ou títulos.
        """
        print("Tentativas encontradas:", len(tentativas))

        print("Enviando prompt para IA...")

        resposta_ia = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        print("Resposta recebida da IA")
        return jsonify({
            "id_aluno": id_aluno,
            "devolutiva": resposta_ia.text
        })

    except Exception as erro:
        import traceback
        traceback.print_exc()

        return jsonify({
            "erro": str(erro)
        }), 500

# ================================================
# DEVOLUTIVA INDIVIDUAL DO ALUNO PARA O PROFESSOR
# ================================================

@app.route("/devolutiva-professor/<int:id_aluno>", methods=["GET"])
def devolutiva_professor(id_aluno):
    try:
        resposta = supabase.table("tentativas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()

        tentativas = resposta.data

        if not tentativas:
            return jsonify({
                "erro": "Aluno sem tentativas"
            }), 404

        total = len(tentativas)

        acertos = sum(
            1 for t in tentativas
            if t["correta"]
        )

        erros = total - acertos

        percentual = round(
            (acertos / total) * 100,
            2
        )

        tipos_erro = [
            t["tipo_erro"]
            for t in tentativas
            if t["tipo_erro"]
        ]

        prompt = f"""
        Você é um coordenador pedagógico especialista em matemática.

        Analise os dados do aluno:

        Total de tentativas: {total}
        Acertos: {acertos}
        Erros: {erros}
        Percentual de acerto: {percentual}%

        Tipos de erro encontrados:
        {tipos_erro}

        Gere uma análise para o professor contendo:

        - Desempenho geral do aluno.
        - Principais dificuldades observadas.
        - Possíveis causas das dificuldades.
        - Recomendações pedagógicas para intervenção.

        Responda em no máximo 8 linhas.
        Utilize linguagem profissional e objetiva.
        """
        resposta_ia = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        return jsonify({
            "id_aluno": id_aluno,
            "analise_professor": resposta_ia.text
        })

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500
    
# ===========================================
# DEVOLUTIVA GERAL DA TURMA PARA O PROFESSOR
# ===========================================

@app.route("/devolutiva-turma/<int:id_turma>", methods=["GET"])
def devolutiva_turma(id_turma):
    try:
        alunos = supabase.table("usuarios") \
            .select("*") \
            .eq("id_turma", id_turma) \
            .execute()

        lista_alunos = alunos.data

        if not lista_alunos:
            return jsonify({
                "erro": "Turma não encontrada"
            }), 404

        total_tentativas = 0
        total_acertos = 0
        total_erros = 0

        for aluno in lista_alunos:

            tentativas = supabase.table("tentativas") \
                .select("*") \
                .eq("id_aluno", aluno["id"]) \
                .execute()

            for tentativa in tentativas.data:

                total_tentativas += 1

                if tentativa["correta"]:
                    total_acertos += 1
                else:
                    total_erros += 1

        percentual = 0

        if total_tentativas > 0:
            percentual = round(
                (total_acertos / total_tentativas) * 100,
                2
            )

        tipos_erro_turma = []
        for aluno in lista_alunos:

            tentativas = supabase.table("tentativas") \
                .select("*") \
                .eq("id_aluno", aluno["id"]) \
                .execute()

            for tentativa in tentativas.data:

                if tentativa["tipo_erro"]:
                    tipos_erro_turma.append(
                        tentativa["tipo_erro"]
                    )

        prompt = f"""
        Você é um coordenador pedagógico especialista em matemática.

        Analise os dados da turma:

        Total de alunos: {len(lista_alunos)}
        Total de tentativas: {total_tentativas}
        Acertos: {total_acertos}
        Erros: {total_erros}
        Principais erros identificados na turma:
        {tipos_erro_turma}
        Percentual médio de acerto: {percentual}%

        Gere uma análise para o professor contendo:

        - Visão geral do desempenho da turma.
        - Possíveis dificuldades coletivas.
        - Pontos fortes observados.
        - Sugestões de intervenção pedagógica.
        - Sugestões para reforço dos conteúdos.

        Responda em no máximo 10 linhas.
        Utilize linguagem clara e profissional.
        """

        resposta_ia = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        return jsonify({
            "id_turma": id_turma,
            "devolutiva_turma": resposta_ia.text
        })

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# ERROS
# ==========================

@app.errorhandler(404)
def erro404(error):

    return jsonify({
        "erro": "URL não encontrada"
    }), 404

@app.errorhandler(500)
def erro500(error):

    return jsonify({
        "erro": "Erro interno no servidor"
    }), 500

if __name__ == "__main__":
    app.run(debug=True) 