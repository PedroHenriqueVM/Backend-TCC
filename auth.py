from flask import Blueprint, request, jsonify
from supabase_client import supabase
from werkzeug.security import check_password_hash
import jwt
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint("auth", __name__)

SECRET_KEY = os.getenv("SECRET_KEY")


# ==========================
# LOGIN
# ==========================

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

        token = jwt.encode({
            "id": usuario["id"],
            "email": usuario["email"],
            "tipo_usuario": usuario["tipo_usuario"],
            "exp": datetime.utcnow() + timedelta(hours=2)
        }, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "mensagem": "Login realizado com sucesso",
            "token": token
        }), 200

    except:
        return jsonify({
            "erro": "Falha no login"
        }), 500