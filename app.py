from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from flasgger import Swagger
from auth import auth_bp
import random
import string
from werkzeug.security import generate_password_hash

from supabase_client import supabase

import os

load_dotenv()

app = Flask(__name__)

app.config['SWAGGER'] = {
    'openapi': '3.0.3'
}

swagger = Swagger(app)

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

    senha_hash = generate_password_hash(senha)

    try:

        supabase.table("usuarios").insert({
            "nome": nome,
            "email": email,
            "senha": senha_hash,
            "tipo_usuario": tipo_usuario
        }).execute()

        return jsonify({
            "mensagem": "Usuário cadastrado com sucesso"
        }), 201

    except:
        return jsonify({
            "erro": "Falha ao cadastrar usuário"
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

    if not nome or not id_professor:
        return jsonify({
            "erro": "Nome da turma e id_professor são obrigatórios"
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
            "id_professor": id_professor
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