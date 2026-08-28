from flask import Flask, jsonify, request, send_file
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
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
import io

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
# ESCOLHER AVATAR
# ==========================

@app.route("/usuarios/<int:id>/avatar", methods=["PUT"])
def escolher_avatar(id):

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    avatar = dados.get("avatar")

    avatares_permitidos = [
        "silas",
        "martim",
        "bento",
        "clarice",
        "tadeu"
    ]

    if avatar not in avatares_permitidos:
        return jsonify({
            "erro": "Avatar inválido",
            "avatares_disponiveis": avatares_permitidos
        }), 400

    try:

        usuario = supabase.table("usuarios") \
            .select("id, nome, email") \
            .eq("id", id) \
            .execute()

        if not usuario.data:
            return jsonify({
                "erro": "Usuário não encontrado"
            }), 404

        supabase.table("usuarios") \
            .update({
                "avatar": avatar
            }) \
            .eq("id", id) \
            .execute()

        return jsonify({
            "mensagem": "Avatar atualizado com sucesso",
            "id_usuario": id,
            "avatar": avatar
        }), 200

    except Exception as erro:

        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# BUSCAR AVATAR DO USUÁRIO
# ==========================

@app.route("/usuarios/<int:id>/avatar", methods=["GET"])
def get_avatar(id):

    try:

        resposta = supabase.table("usuarios") \
            .select("id, nome, avatar") \
            .eq("id", id) \
            .execute()

        if not resposta.data:
            return jsonify({
                "erro": "Usuário não encontrado"
            }), 404

        usuario = resposta.data[0]

        return jsonify({
            "id": usuario["id"],
            "nome": usuario["nome"],
            "avatar": usuario["avatar"]
        }), 200

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
# REDEFINIR SENHA DO ALUNO
# ==========================

@app.route("/redefinir-senha", methods=["POST"])
def redefinir_senha():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    id_aluno = dados.get("id_aluno")

    if not id_aluno:
        return jsonify({
            "erro": "id_aluno é obrigatório"
        }), 400

    try:

        # Verifica se o aluno existe
        aluno = supabase.table("usuarios") \
            .select("*") \
            .eq("id", id_aluno) \
            .eq("tipo_usuario", "aluno") \
            .execute()

        if not aluno.data:
            return jsonify({
                "erro": "Aluno não encontrado"
            }), 404

        # Gera senha temporária
        senha_temporaria = (
            "Fracta" +
            ''.join(
                random.choices(
                    string.ascii_letters + string.digits,
                    k=5
                )
            )
        )

        senha_hash = generate_password_hash(senha_temporaria)

        # Atualiza a senha e obriga a alteração
        supabase.table("usuarios") \
            .update({
                "senha": senha_hash,
                "precisa_alterar_senha": True
            }) \
            .eq("id", id_aluno) \
            .execute()

        return jsonify({
            "mensagem": "Senha redefinida com sucesso",
            "senha_temporaria": senha_temporaria
        }), 200

    except Exception as erro:

        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# ALTERAR SENHA
# ==========================

@app.route("/alterar-senha", methods=["POST"])
def alterar_senha():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    id_aluno = dados.get("id_aluno")
    senha_atual = dados.get("senha_atual")
    nova_senha = dados.get("nova_senha")

    if not id_aluno or not senha_atual or not nova_senha:
        return jsonify({
            "erro": "id_aluno, senha_atual e nova_senha são obrigatórios"
        }), 400

    if len(nova_senha) < 6:
        return jsonify({
            "erro": "A nova senha deve ter pelo menos 6 caracteres"
        }), 400

    try:

        # Busca o aluno
        resposta = supabase.table("usuarios") \
            .select("*") \
            .eq("id", id_aluno) \
            .eq("tipo_usuario", "aluno") \
            .execute()

        if not resposta.data:
            return jsonify({
                "erro": "Aluno não encontrado"
            }), 404

        aluno = resposta.data[0]

        # Verifica a senha atual
        from werkzeug.security import check_password_hash

        senha_correta = check_password_hash(
            aluno["senha"],
            senha_atual
        )

        if not senha_correta:
            return jsonify({
                "erro": "Senha atual incorreta"
            }), 401

        # Gera o hash da nova senha
        nova_senha_hash = generate_password_hash(nova_senha)

        # Atualiza a senha
        supabase.table("usuarios") \
            .update({
                "senha": nova_senha_hash,
                "precisa_alterar_senha": False
            }) \
            .eq("id", id_aluno) \
            .execute()

        return jsonify({
            "mensagem": "Senha alterada com sucesso"
        }), 200

    except Exception as erro:

        return jsonify({
            "erro": str(erro)
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
# GERAR QUESTÕES POR CAPÍTULO
# ==========================

@app.route("/gerar-questoes/<int:id_capitulo>", methods=["POST"])
def gerar_questoes(id_capitulo):

    try:

        # Busca o capítulo
        resposta = supabase.table("capitulos") \
            .select("*") \
            .eq("id", id_capitulo) \
            .execute()

        if not resposta.data:
            return jsonify({
                "erro": "Capítulo não encontrado"
            }), 404

        capitulo = resposta.data[0]

        titulo = capitulo["titulo"]
        conteudo = capitulo["conteudo"]

        if not conteudo:
            return jsonify({
                "erro": "Este capítulo não possui conteúdo cadastrado"
            }), 400

        # Prompt enviado para a IA
        prompt = f"""
Você é um professor de matemática especializado no ensino
de alunos do 6º ano do Ensino Fundamental.

Crie 20 questões de matemática baseadas EXCLUSIVAMENTE
nos conteúdos deste capítulo.

TRILHA:
Aventuras de Silas — O Mistério das Frações

CAPÍTULO:
{titulo}

CONTEÚDOS:
{conteudo}

As questões devem:

- Ser adequadas para alunos do 6º ano.
- Estar relacionadas diretamente aos conteúdos informados.
- Possuir diferentes níveis de dificuldade.
- Não utilizar conteúdos que não estejam relacionados ao capítulo.
- Ter uma única resposta correta.
- Utilizar linguagem clara e adequada para estudantes.

Retorne SOMENTE um JSON válido no seguinte formato:

[
    {{
        "pergunta": "pergunta da questão",
        "resposta_correta": "resposta correta",
        "categoria": "conteúdo relacionado",
        "nivel": "fácil"
    }}
]

Os níveis permitidos são:
fácil, médio ou difícil.
"""
        # Gera as questões
        resposta_ia = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        texto = resposta_ia.text

        # Remove possíveis blocos de markdown
        texto = texto.replace("```json", "")
        texto = texto.replace("```", "")
        texto = texto.strip()

        import json

        questoes = json.loads(texto)

        # Salva as questões no banco
        questoes_salvas = []

        for questao in questoes:
            resultado = supabase.table("exercicios").insert({
                "pergunta": questao["pergunta"],
                "resposta_correta": questao["resposta_correta"],
                "categoria": questao["categoria"],
                "nivel": questao["nivel"],
                "id_capitulo": id_capitulo
            }).execute()

            if resultado.data:
                questoes_salvas.append(resultado.data[0])

        return jsonify({
            "mensagem": "Questões geradas com sucesso",
            "id_capitulo": id_capitulo,
            "capitulo": titulo,
            "quantidade": len(questoes_salvas),
            "questoes": questoes_salvas
        }), 201

    except json.JSONDecodeError:
        return jsonify({
            "erro": "A IA retornou um formato inválido"
        }), 500

    except Exception as erro:

        return jsonify({
            "erro": str(erro)
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
# CRIAR TURMA
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

    if not nome or not id_professor or not id_trilha:
        return jsonify({
            "erro": "Nome da turma, id_professor e id_trilha são obrigatórios"
        }), 400

    try:
        # Verifica se o professor existe
        professor = supabase.table("usuarios") \
            .select("*") \
            .eq("id", id_professor) \
            .eq("tipo_usuario", "professor") \
            .execute()

        if not professor.data:
            return jsonify({
                "erro": "Professor não encontrado"
            }), 404

        # Verifica se a trilha existe
        trilha = supabase.table("trilhas") \
            .select("*") \
            .eq("id", id_trilha) \
            .execute()

        if not trilha.data:
            return jsonify({
                "erro": "Trilha não encontrada"
            }), 404

        # Gera código aleatório de 6 caracteres
        codigo = ''.join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )

        # Cria a turma
        supabase.table("turmas").insert({
            "nome": nome,
            "codigo": codigo,
            "id_professor": id_professor,
            "id_trilha": id_trilha
        }).execute()
        return jsonify({
            "mensagem": "Turma criada com sucesso",
            "codigo": codigo,
            "id_trilha": id_trilha,
            "trilha": trilha.data[0]["nome"]
        }), 201

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# BUSCAR TRILHA DA TURMA
# ==========================

@app.route("/turmas/<int:id_turma>/trilha", methods=["GET"])
def get_trilha_turma(id_turma):

    try:

        # Busca a turma
        turma = supabase.table("turmas") \
            .select("*") \
            .eq("id", id_turma) \
            .execute()

        if not turma.data:
            return jsonify({
                "erro": "Turma não encontrada"
            }), 404

        turma = turma.data[0]

        # Verifica se a turma possui uma trilha
        if not turma.get("id_trilha"):
            return jsonify({
                "erro": "Esta turma não possui uma trilha"
            }), 404

        # Busca a trilha
        trilha = supabase.table("trilhas") \
            .select("*") \
            .eq("id", turma["id_trilha"]) \
            .execute()

        if not trilha.data:
            return jsonify({
                "erro": "Trilha não encontrada"
            }), 404

        trilha = trilha.data[0]

        # Busca os capítulos
        capitulos = supabase.table("capitulos") \
            .select("*") \
            .eq("id_trilha", trilha["id"]) \
            .order("ordem") \
            .execute()

        return jsonify({
            "turma": {
                "id": turma["id"],
                "nome": turma["nome"],
                "codigo": turma["codigo"]
            },
            "trilha": trilha,
            "capitulos": capitulos.data
        }), 200

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
# LISTAR TODAS AS TRILHAS
# ==========================

@app.route("/trilhas", methods=["GET"])
def get_trilhas():
    try:
        resposta = supabase.table("trilhas") \
            .select("*") \
            .order("id") \
            .execute()

        return jsonify(resposta.data), 200

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ==========================
# LISTAR TRILHA POR ID
# ==========================

@app.route("/trilhas/<int:id_trilha>", methods=["GET"])
def get_trilha(id_trilha):

    try:

        # Busca a trilha
        trilha = supabase.table("trilhas") \
            .select("*") \
            .eq("id", id_trilha) \
            .execute()

        if not trilha.data:
            return jsonify({
                "erro": "Trilha não encontrada"
            }), 404

        trilha = trilha.data[0]

        # Busca os capítulos da trilha
        capitulos = supabase.table("capitulos") \
            .select("*") \
            .eq("id_trilha", id_trilha) \
            .order("ordem") \
            .execute()

        return jsonify({
            "trilha": trilha,
            "capitulos": capitulos.data
        }), 200

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

# ============================================
# RELATÓRIO INDIVIDUAL DO ALUNO EM PDF
# ============================================

@app.route("/relatorio-aluno/<int:id_aluno>", methods=["GET"])
def relatorio_aluno_pdf(id_aluno):

    try:

        # =====================================
        # BUSCAR ALUNO
        # =====================================

        aluno_resposta = supabase.table("usuarios") \
            .select("id, nome, email, id_turma") \
            .eq("id", id_aluno) \
            .eq("tipo_usuario", "aluno") \
            .execute()

        if not aluno_resposta.data:
            return jsonify({
                "erro": "Aluno não encontrado"
            }), 404

        aluno = aluno_resposta.data[0]

        # =====================================
        # BUSCAR TURMA
        # =====================================

        turma_nome = "Não informado"

        if aluno.get("id_turma"):

            turma_resposta = supabase.table("turmas") \
                .select("nome") \
                .eq("id", aluno["id_turma"]) \
                .execute()

            if turma_resposta.data:
                turma_nome = turma_resposta.data[0]["nome"]

        # =====================================
        # BUSCAR TENTATIVAS
        # =====================================

        tentativas_resposta = supabase.table("tentativas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()

        tentativas = tentativas_resposta.data

        if not tentativas:

            return jsonify({
                "erro": "Aluno ainda não possui tentativas registradas"
            }), 404

        # =====================================
        # CALCULAR DESEMPENHO
        # =====================================

        total = len(tentativas)

        acertos = sum(
            1 for tentativa in tentativas
            if tentativa["correta"]
        )

        erros = total - acertos

        percentual = round(
            (acertos / total) * 100,
            2
        )

        # =====================================
        # DESEMPENHO POR CATEGORIA
        # =====================================

        categorias = {}

        for tentativa in tentativas:

            exercicio_resposta = supabase.table("exercicios") \
                .select("categoria") \
                .eq("id", tentativa["id_exercicio"]) \
                .execute()

            if not exercicio_resposta.data:
                continue

            categoria = exercicio_resposta.data[0]["categoria"]

            if categoria not in categorias:

                categorias[categoria] = {
                    "total": 0,
                    "acertos": 0,
                    "erros": 0
                }

            categorias[categoria]["total"] += 1

            if tentativa["correta"]:
                categorias[categoria]["acertos"] += 1
            else:
                categorias[categoria]["erros"] += 1

        # =====================================
        # CALCULAR PERCENTUAIS DOS TEMAS
        # =====================================

        melhor_tema = None
        pior_tema = None

        maior_percentual = -1
        menor_percentual = 101

        for categoria, dados in categorias.items():

            percentual_categoria = round(
                (dados["acertos"] / dados["total"]) * 100,
                2
            )

            dados["percentual"] = percentual_categoria

            if percentual_categoria > maior_percentual:

                maior_percentual = percentual_categoria
                melhor_tema = categoria

            if percentual_categoria < menor_percentual:

                menor_percentual = percentual_categoria
                pior_tema = categoria

        # =====================================
        # FEEDBACK
        # =====================================

        if percentual >= 80:

            feedback = (
                "O aluno apresenta excelente desempenho "
                "nas atividades realizadas."
            )

        elif percentual >= 60:

            feedback = (
                "O aluno apresenta um bom desempenho, "
                "mas ainda possui conteúdos que precisam "
                "ser reforçados."
            )

        else:

            feedback = (
                "O aluno apresenta dificuldades nos conteúdos "
                "avaliados. Recomenda-se reforçar os conceitos "
                "básicos e realizar novas atividades."
            )

        # =====================================
        # CRIAR PDF
        # =====================================

        buffer = io.BytesIO()

        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )

        estilos = getSampleStyleSheet()

        titulo = ParagraphStyle(
            "Titulo",
            parent=estilos["Title"],
            alignment=TA_CENTER,
            fontSize=22,
            spaceAfter=20
        )

        subtitulo = ParagraphStyle(
            "Subtitulo",
            parent=estilos["Heading2"],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10
        )

        texto = ParagraphStyle(
            "Texto",
            parent=estilos["BodyText"],
            fontSize=10,
            leading=15
        )

        elementos = []

        # =====================================
        # CABEÇALHO
        # =====================================

        elementos.append(
            Paragraph("FRACTA", titulo)
        )

        elementos.append(
            Paragraph(
                "Relatório Individual de Desempenho",
                subtitulo
            )
        )

        elementos.append(
            Paragraph(
                f"<b>Aluno:</b> {aluno['nome']}<br/>"
                f"<b>E-mail:</b> {aluno['email']}<br/>"
                f"<b>Turma:</b> {turma_nome}",
                texto
            )
        )

        elementos.append(Spacer(1, 15))

        # =====================================
        # RESUMO
        # =====================================

        elementos.append(
            Paragraph(
                "Resumo do desempenho",
                subtitulo
            )
        )

        resumo = [
            ["Indicador", "Resultado"],
            ["Questões respondidas", str(total)],
            ["Acertos", str(acertos)],
            ["Erros", str(erros)],
            ["Aproveitamento", f"{percentual}%"]
        ]

        tabela_resumo = Table(
            resumo,
            colWidths=[9 * cm, 7 * cm]
        )

        tabela_resumo.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C56E33")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
            ])
        )

        elementos.append(tabela_resumo)

        # =====================================
        # TEMAS
        # =====================================

        elementos.append(
            Paragraph(
                "Desempenho por tema",
                subtitulo
            )
        )

        dados_temas = [
            [
                "Tema",
                "Questões",
                "Acertos",
                "Erros",
                "Aproveitamento"
            ]
        ]

        for categoria, dados in categorias.items():

            dados_temas.append([
                categoria,
                str(dados["total"]),
                str(dados["acertos"]),
                str(dados["erros"]),
                f"{dados['percentual']}%"
            ])

        tabela_temas = Table(
            dados_temas,
            colWidths=[
                6 * cm,
                2.3 * cm,
                2.3 * cm,
                2.3 * cm,
                3 * cm
            ]
        )

        tabela_temas.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C56E33")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )

        elementos.append(tabela_temas)

        # =====================================
        # ANÁLISE
        # =====================================

        elementos.append(
            Paragraph(
                "Análise pedagógica",
                subtitulo
            )
        )

        if melhor_tema:

            elementos.append(
                Paragraph(
                    f"<b>Melhor desempenho:</b> "
                    f"{melhor_tema} ({maior_percentual}%).",
                    texto
                )
            )

        if pior_tema:

            elementos.append(
                Paragraph(
                    f"<b>Maior dificuldade:</b> "
                    f"{pior_tema} ({menor_percentual}%).",
                    texto
                )
            )

        elementos.append(Spacer(1, 10))

        elementos.append(
            Paragraph(
                feedback,
                texto
            )
        )

        # =====================================
        # RECOMENDAÇÕES
        # =====================================
        elementos.append(
            Paragraph(
                "Recomendações",
                subtitulo
            )
        )

        if pior_tema:
            recomendacao = (
                f"Recomenda-se reforçar principalmente "
                f"o conteúdo de <b>{pior_tema}</b>, "
                f"realizando atividades adicionais e "
                f"acompanhando a evolução do aluno."
            )
        else:
            recomendacao = (
                "Recomenda-se continuar acompanhando "
                "o desempenho do aluno nas próximas atividades."
            )
        elementos.append(
            Paragraph(
                recomendacao,
                texto
            )
        )

        # =====================================
        # GERAR PDF
        # =====================================
        documento.build(elementos)
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"relatorio_{aluno['nome']}.pdf"
        )

    except Exception as erro:
        return jsonify({
            "erro": str(erro)
        }), 500

# ============================================
# RELATÓRIO DA TURMA EM PDF
# ============================================

@app.route("/relatorio-turma/<int:id_turma>", methods=["GET"])
def relatorio_turma_pdf(id_turma):
    try:
        # =====================================
        # BUSCAR TURMA
        # =====================================
        turma_resposta = supabase.table("turmas") \
            .select("*") \
            .eq("id", id_turma) \
            .execute()
        if not turma_resposta.data:
            return jsonify({
                "erro": "Turma não encontrada"
            }), 404
        turma = turma_resposta.data[0]

        # =====================================
        # BUSCAR PROFESSOR
        # =====================================
        professor_nome = "Não informado"
        if turma.get("id_professor"):
            professor = supabase.table("usuarios") \
                .select("nome") \
                .eq("id", turma["id_professor"]) \
                .eq("tipo_usuario", "professor") \
                .execute()
            if professor.data:
                professor_nome = professor.data[0]["nome"]

        # =====================================
        # BUSCAR ALUNOS DA TURMA
        # =====================================
        alunos_resposta = supabase.table("usuarios") \
            .select("id, nome, email") \
            .eq("id_turma", id_turma) \
            .eq("tipo_usuario", "aluno") \
            .execute()
        alunos = alunos_resposta.data
        if not alunos:
            return jsonify({
                "erro": "A turma ainda não possui alunos"
            }), 404

        # =====================================
        # VARIÁVEIS GERAIS
        # =====================================
        total_tentativas = 0
        total_acertos = 0
        total_erros = 0

        desempenho_alunos = {}

        categorias = {}

        # =====================================
        # ANALISAR CADA ALUNO
        # =====================================
        for aluno in alunos:
            tentativas_resposta = supabase.table("tentativas") \
                .select("*") \
                .eq("id_aluno", aluno["id"]) \
                .execute()
            tentativas = tentativas_resposta.data
            aluno_total = len(tentativas)
            aluno_acertos = sum(
                1 for tentativa in tentativas
                if tentativa["correta"]
            )
            aluno_erros = aluno_total - aluno_acertos
            if aluno_total > 0:
                aluno_percentual = round(
                    (aluno_acertos / aluno_total) * 100,
                    2
                )
            else:
                aluno_percentual = 0
            desempenho_alunos[aluno["id"]] = {
                "nome": aluno["nome"],
                "total": aluno_total,
                "acertos": aluno_acertos,
                "erros": aluno_erros,
                "percentual": aluno_percentual
            }
            total_tentativas += aluno_total
            total_acertos += aluno_acertos
            total_erros += aluno_erros

            # =================================
            # CATEGORIAS
            # =================================
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
                        "total": 0,
                        "acertos": 0,
                        "erros": 0
                    }

                categorias[categoria]["total"] += 1
                if tentativa["correta"]:
                    categorias[categoria]["acertos"] += 1
                else:
                    categorias[categoria]["erros"] += 1

        # =====================================
        # MÉDIA DA TURMA
        # =====================================
        if total_tentativas > 0:
            percentual_turma = round(
                (total_acertos / total_tentativas) * 100,
                2
            )

        else:
            percentual_turma = 0

        # =====================================
        # PERCENTUAIS DOS TEMAS
        # =====================================
        melhor_tema = None
        pior_tema = None

        maior_percentual = -1
        menor_percentual = 101

        for categoria, dados in categorias.items():
            percentual_categoria = round(
                (dados["acertos"] / dados["total"]) * 100,
                2
            )
            dados["percentual"] = percentual_categoria
            if percentual_categoria > maior_percentual:
                maior_percentual = percentual_categoria
                melhor_tema = categoria
            if percentual_categoria < menor_percentual:
                menor_percentual = percentual_categoria
                pior_tema = categoria

        # =====================================
        # ORDENAR RANKING
        # =====================================
        ranking = sorted(
            desempenho_alunos.values(),
            key=lambda aluno: aluno["percentual"],
            reverse=True
        )

        # =====================================
        # CRIAR PDF
        # =====================================
        buffer = io.BytesIO()
        documento = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )
        estilos = getSampleStyleSheet()
        titulo = ParagraphStyle(
            "TituloTurma",
            parent=estilos["Title"],
            alignment=TA_CENTER,
            fontSize=22,
            spaceAfter=20
        )
        subtitulo = ParagraphStyle(
            "SubtituloTurma",
            parent=estilos["Heading2"],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10
        )
        texto = ParagraphStyle(
            "TextoTurma",
            parent=estilos["BodyText"],
            fontSize=10,
            leading=15
        )

        elementos = []

        # =====================================
        # CABEÇALHO
        # =====================================
        elementos.append(
            Paragraph(
                "FRACTA",
                titulo
            )
        )
        elementos.append(
            Paragraph(
                "Relatório de Desempenho da Turma",
                subtitulo
            )
        )
        elementos.append(
            Paragraph(
                f"<b>Turma:</b> {turma['nome']}<br/>"
                f"<b>Professor:</b> {professor_nome}<br/>"
                f"<b>Total de alunos:</b> {len(alunos)}",
                texto
            )
        )

        elementos.append(Spacer(1, 15))

        # =====================================
        # RESUMO
        # =====================================
        elementos.append(
            Paragraph(
                "Resumo geral",
                subtitulo
            )
        )
        resumo = [
            ["Indicador", "Resultado"],
            ["Alunos", str(len(alunos))],
            ["Questões respondidas", str(total_tentativas)],
            ["Acertos", str(total_acertos)],
            ["Erros", str(total_erros)],
            ["Aproveitamento da turma", f"{percentual_turma}%"]
        ]
        tabela_resumo = Table(
            resumo,
            colWidths=[9 * cm, 7 * cm]
        )
        tabela_resumo.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C56E33")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
            ])
        )

        elementos.append(tabela_resumo)

        # =====================================
        # DESEMPENHO POR TEMA
        # =====================================
        elementos.append(
            Paragraph(
                "Desempenho por tema",
                subtitulo
            )
        )
        dados_temas = [
            [
                "Tema",
                "Questões",
                "Acertos",
                "Erros",
                "Aproveitamento"
            ]
        ]

        for categoria, dados in categorias.items():
            dados_temas.append([
                categoria,
                str(dados["total"]),
                str(dados["acertos"]),
                str(dados["erros"]),
                f"{dados['percentual']}%"
            ])

        if len(dados_temas) > 1:
            tabela_temas = Table(
                dados_temas,
                colWidths=[
                    6 * cm,
                    2.3 * cm,
                    2.3 * cm,
                    2.3 * cm,
                    3 * cm
                ]
            )

            tabela_temas.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C56E33")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ])
            )

            elementos.append(tabela_temas)

        # =====================================
        # RANKING
        # =====================================

        elementos.append(
            Paragraph(
                "Desempenho dos alunos",
                subtitulo
            )
        )

        dados_ranking = [
            [
                "Posição",
                "Aluno",
                "Questões",
                "Acertos",
                "Aproveitamento"
            ]
        ]

        for posicao, aluno in enumerate(ranking, start=1):
            dados_ranking.append([
                str(posicao),
                aluno["nome"],
                str(aluno["total"]),
                str(aluno["acertos"]),
                f"{aluno['percentual']}%"
            ])

        tabela_ranking = Table(
            dados_ranking,
            colWidths=[
                1.5 * cm,
                7 * cm,
                2.5 * cm,
                2.5 * cm,
                3 * cm
            ]
        )

        tabela_ranking.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C56E33")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ])
        )

        elementos.append(tabela_ranking)

        # =====================================
        # ANÁLISE
        # =====================================

        elementos.append(
            Paragraph(
                "Análise da turma",
                subtitulo
            )
        )

        if melhor_tema:
            elementos.append(
                Paragraph(
                    f"<b>Melhor desempenho coletivo:</b> "
                    f"{melhor_tema} ({maior_percentual}%).",
                    texto
                )
            )

        if pior_tema:
            elementos.append(
                Paragraph(
                    f"<b>Maior dificuldade coletiva:</b> "
                    f"{pior_tema} ({menor_percentual}%).",
                    texto
                )
            )

        elementos.append(Spacer(1, 10))

        if percentual_turma >= 80:
            analise = (
                "A turma apresenta excelente desempenho geral. "
                "Os resultados indicam bom domínio dos conteúdos."
            )
        elif percentual_turma >= 60:

            analise = (
                "A turma apresenta desempenho satisfatório, "
                "porém alguns conteúdos precisam ser reforçados."
            )
        else:
            analise = (
                "A turma apresenta dificuldades nos conteúdos "
                "avaliados. Recomenda-se reforçar os conceitos "
                "fundamentais e realizar atividades adicionais."
            )
        elementos.append(
            Paragraph(
                analise,
                texto
            )
        )

        # =====================================
        # RECOMENDAÇÕES
        # =====================================

        elementos.append(
            Paragraph(
                "Recomendações para o professor",
                subtitulo
            )
        )

        if pior_tema:
            recomendacao = (
                f"Recomenda-se trabalhar novamente o conteúdo "
                f"de <b>{pior_tema}</b>, utilizando atividades "
                f"de reforço e acompanhamento individual dos "
                f"alunos que apresentaram menor desempenho."
            )
        else:
            recomendacao = (
                "Recomenda-se continuar acompanhando o "
                "desempenho da turma e realizar novas avaliações."
            )
        elementos.append(
            Paragraph(
                recomendacao,
                texto
            )
        )

        # =====================================
        # GERAR PDF
        # =====================================
        documento.build(elementos)
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"relatorio_turma_{turma['nome']}.pdf"
        )

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