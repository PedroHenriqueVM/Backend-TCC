
from flask import Blueprint, request, jsonify
from supabase_client import supabase
from werkzeug.security import check_password_hash
from functools import wraps
import jwt
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint("auth", __name__)
SECRET_KEY = os.getenv("SECRET_KEY")


# ==========================================
# VALIDAR TOKEN JWT
# ==========================================

def token_obrigatorio(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):

        cabecalho = request.headers.get("Authorization", "")

        if not cabecalho.startswith("Bearer "):
            return jsonify({
                "erro": "Token não enviado"
            }), 401

        token = cabecalho.split(" ", 1)[1]
    
        try:
            dados_token = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=["HS256"]
            )

            request.usuario = dados_token

        except jwt.ExpiredSignatureError:
            return jsonify({
                "erro": "Token expirado. Faça login novamente."
            }), 401

        except jwt.InvalidTokenError:
            return jsonify({
                "erro": "Token inválido"
            }), 401

        return funcao(*args, **kwargs)

    return decorada

# ==========================================
# PERMITIR ACESSO SOMENTE A PROFESSORES
# ==========================================

def professor_obrigatorio(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):

        if request.usuario.get("tipo_usuario") != "professor":
            return jsonify({
                "erro": "Acesso permitido somente para professores"
            }), 403

        return funcao(*args, **kwargs)

    return decorada

# ==========================================
# LOGIN
# ==========================================

@auth_bp.route("/login", methods=["POST"])
def login():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    email = dados.get("email")
    senha = dados.get("senha")

    if not email or not senha:
        return jsonify({
            "erro": "Email e senha são obrigatórios"
        }), 400

    try:

        resposta = supabase.table("usuarios") \
            .select("*") \
            .eq("email", email) \
            .execute()

        if not resposta.data:
            return jsonify({
                "erro": "Usuário não encontrado"
            }), 404

        usuario = resposta.data[0]

        senha_correta = check_password_hash(
            usuario["senha"],
            senha
        )

        if not senha_correta:
            return jsonify({
                "erro": "Senha incorreta"
            }), 401

        if not SECRET_KEY:
            return jsonify({
                "erro": "SECRET_KEY não configurada no servidor"
            }), 500

        token = jwt.encode({
            "id": usuario["id"],
            "email": usuario["email"],
            "tipo_usuario": usuario["tipo_usuario"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=2)
        }, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "mensagem": "Login realizado com sucesso",
            "token": token,
            "usuario": {
                "id": usuario["id"],
                "nome": usuario["nome"],
                "email": usuario["email"],
                "tipo_usuario": usuario["tipo_usuario"]
            }
        }), 200

    except Exception as erro:
        print("Erro no login:", erro)

        return jsonify({
            "erro": "Falha no login"
        }), 500
