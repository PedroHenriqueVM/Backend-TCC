from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from flasgger import Swagger
from auth import auth_bp, token_obrigatorio
from datetime import datetime, timezone
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


# ==========================================
# SISTEMA DE XP E CONQUISTAS
# ==========================================

def registrar_xp(id_aluno, quantidade, origem, evento_chave,
                 descricao, referencia_tipo=None, referencia_id=None):

    # Evita entregar XP duas vezes pelo mesmo evento
    existente = supabase.table("historico_xp") \
        .select("id") \
        .eq("id_aluno", id_aluno) \
        .eq("origem", origem) \
        .eq("evento_chave", evento_chave) \
        .execute()

    if existente.data:
        return False

    supabase.table("historico_xp").insert({
        "id_aluno": id_aluno,
        "quantidade": quantidade,
        "origem": origem,
        "evento_chave": evento_chave,
        "descricao": descricao,
        "referencia_tipo": referencia_tipo,
        "referencia_id": referencia_id
    }).execute()

    return True


def verificar_conquistas(id_aluno):

    # Conta os acertos do aluno
    tentativas = supabase.table("tentativas") \
        .select("id") \
        .eq("id_aluno", id_aluno) \
        .eq("correta", True) \
        .execute()

    total_acertos = len(tentativas.data)

    # Conta as partidas
    partidas = supabase.table("partidas") \
        .select("id") \
        .eq("id_aluno", id_aluno) \
        .execute()

    total_partidas = len(partidas.data)

    # Calcula o XP atual
    historico = supabase.table("historico_xp") \
        .select("quantidade") \
        .eq("id_aluno", id_aluno) \
        .execute()

    total_xp = sum(
        item["quantidade"] for item in historico.data
    )

    # Busca as conquistas disponíveis
    conquistas = supabase.table("conquistas") \
        .select("*") \
        .eq("ativa", True) \
        .execute()

    # Busca as conquistas já desbloqueadas
    desbloqueadas = supabase.table("conquistas_aluno") \
        .select("id_conquista") \
        .eq("id_aluno", id_aluno) \
        .execute()

    ids_desbloqueados = [
        item["id_conquista"] for item in desbloqueadas.data
    ]

    novas_conquistas = []

    for conquista in conquistas.data:

        if conquista["id"] in ids_desbloqueados:
            continue

        codigo = conquista["codigo"]

        # Verifica os requisitos de cada conquista
        desbloquear = False

        if codigo == "primeiro_acerto":
            desbloquear = total_acertos >= 1

        elif codigo == "dez_acertos":
            desbloquear = total_acertos >= 10

        elif codigo == "primeiro_jogo":
            desbloquear = total_partidas >= 1

        elif codigo == "cinco_partidas":
            desbloquear = total_partidas >= 5

        elif codigo == "cem_xp":
            desbloquear = total_xp >= 100

        if not desbloquear:
            continue

        recompensa = conquista["xp_recompensa"]

        # Registra a conquista do aluno
        supabase.table("conquistas_aluno").insert({
            "id_aluno": id_aluno,
            "id_conquista": conquista["id"],
            "xp_recebido": recompensa
        }).execute()

        # Entrega a recompensa de XP
        if recompensa > 0:
            registrar_xp(
                id_aluno=id_aluno,
                quantidade=recompensa,
                origem="conquista",
                evento_chave=codigo,
                descricao=f"Conquista desbloqueada: {conquista['nome']}",
                referencia_tipo="conquista",
                referencia_id=conquista["id"]
            )

        novas_conquistas.append({
            "codigo": codigo,
            "nome": conquista["nome"],
            "xp_recebido": recompensa
        })

    return novas_conquistas


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

    # Remove espaços do início e do final
    nome = nome.strip()

    # Valida o tamanho e o formato do nome
    import re

    if len(nome) < 3:
        return jsonify({
            "erro": "O nome deve ter pelo menos 3 caracteres"
        }), 400

    if len(nome) > 85:
            return jsonify({
                "erro": "O nome deve ter no máximo 85 caracteres"
            }), 400

    if not re.fullmatch(
        r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '-][A-Za-zÀ-ÖØ-öø-ÿ]+)*",
        nome
    ):
        return jsonify({
            "erro": "Digite um nome válido, usando apenas letras"
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

# ==========================================
# REGISTRAR PARTIDA E ATUALIZAR PROGRESSO
# ==========================================

@app.route("/partidas", methods=["POST"])
@token_obrigatorio
def registrar_partida():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    if request.usuario.get("tipo_usuario") != "aluno":
        return jsonify({
            "erro": "Apenas alunos podem registrar partidas"
        }), 403

    id_aluno = request.usuario["id"]

    jogo = dados.get("jogo")
    pontuacao = dados.get("pontuacao", 0)
    resultado = dados.get("resultado")
    tempo = dados.get("tempo_gasto_segundos")
    fases = dados.get("fases_concluidas", 0)
    estrelas = dados.get("estrelas", 0)
    detalhes = dados.get("detalhes", {})
    fase_atual = dados.get("fase_atual", 1)

    if not jogo:
        return jsonify({
            "erro": "O nome do jogo é obrigatório"
        }), 400

    if not isinstance(detalhes, dict):
        return jsonify({
            "erro": "detalhes deve ser um objeto"
        }), 400

    try:

        pontuacao = int(pontuacao)
        fases = int(fases)
        estrelas = int(estrelas)
        fase_atual = int(fase_atual)

        if pontuacao < 0 or fases < 0 or estrelas < 0 or fase_atual < 1:
            return jsonify({
                "erro": "Os valores numéricos são inválidos"
            }), 400

        if tempo is not None:
            tempo = int(tempo)

            if tempo < 0:
                return jsonify({
                    "erro": "O tempo não pode ser negativo"
                }), 400

        # Registra a partida
        resposta = supabase.table("partidas").insert({
            "id_aluno": id_aluno,
            "jogo": jogo,
            "pontuacao": pontuacao,
            "resultado": resultado,
            "tempo_gasto_segundos": tempo,
            "fases_concluidas": fases,
            "estrelas": estrelas,
            "detalhes": detalhes
        }).execute()

        partida = resposta.data[0]

        # Busca o progresso anterior do jogo
        progresso = supabase.table("progresso_jogos") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .eq("jogo", jogo) \
            .execute()

        if progresso.data:

            anterior = progresso.data[0]

            melhor_pontuacao = max(
                anterior["melhor_pontuacao"],
                pontuacao
            )

            total_partidas = anterior["total_partidas"] + 1

            fases_concluidas = max(
                anterior["fases_concluidas"],
                fases
            )

            fase_atual = max(
                anterior["fase_atual"],
                fase_atual
            )

        else:

            melhor_pontuacao = pontuacao
            total_partidas = 1
            fases_concluidas = fases

        # Atualiza ou cria o progresso do jogo
        supabase.table("progresso_jogos").upsert({
            "id_aluno": id_aluno,
            "jogo": jogo,
            "fases_concluidas": fases_concluidas,
            "fase_atual": fase_atual,
            "melhor_pontuacao": melhor_pontuacao,
            "total_partidas": total_partidas,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
            "dados_extra": detalhes
        }, on_conflict="id_aluno,jogo").execute()

        # Cada registro de partida concluída vale 5 XP
        registrar_xp(
            id_aluno=id_aluno,
            quantidade=5,
            origem="jogo",
            evento_chave=f"partida:{partida['id']}",
            descricao=f"Partida concluída: {jogo}",
            referencia_tipo="partida",
            referencia_id=partida["id"]
        )

        novas_conquistas = verificar_conquistas(id_aluno)

        xp_conquistas = sum(
            item["xp_recebido"] for item in novas_conquistas
        )

        return jsonify({
            "mensagem": "Partida registrada com sucesso",
            "partida": partida,
            "xp_recebido": 5 + xp_conquistas,
            "novas_conquistas": novas_conquistas
        }), 201

    except (ValueError, TypeError):
        return jsonify({
            "erro": "Pontuação, fases, estrelas, tempo e fase atual devem ser números válidos"
        }), 400

    except Exception as erro:
        print("Erro ao registrar partida:", erro)

        return jsonify({
            "erro": "Erro ao registrar partida"
        }), 500


# ==========================================
# CONSULTAR XP DO ALUNO
# ==========================================

@app.route("/me/xp", methods=["GET"])
@token_obrigatorio
def consultar_xp():

    id_aluno = request.usuario["id"]

    try:

        historico = supabase.table("historico_xp") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .order("criado_em", desc=True) \
            .execute()

        total_xp = sum(
            item["quantidade"] for item in historico.data
        )

        return jsonify({
            "id_aluno": id_aluno,
            "xp_total": total_xp,
            "historico": historico.data
        }), 200

    except Exception as erro:
        print("Erro ao consultar XP:", erro)

        return jsonify({
            "erro": "Erro ao consultar XP"
        }), 500


# ==========================================
# CONSULTAR CONQUISTAS DO ALUNO
# ==========================================

@app.route("/me/conquistas", methods=["GET"])
@token_obrigatorio
def consultar_conquistas():

    id_aluno = request.usuario["id"]

    try:

        resposta = supabase.table("conquistas_aluno") \
            .select("*, conquistas(*)") \
            .eq("id_aluno", id_aluno) \
            .order("desbloqueada_em", desc=True) \
            .execute()

        return jsonify({
            "conquistas": resposta.data
        }), 200

    except Exception as erro:
        print("Erro ao consultar conquistas:", erro)

        return jsonify({
            "erro": "Erro ao consultar conquistas"
        }), 500


# ==========================================
# CONSULTAR PROGRESSO DOS JOGOS
# ==========================================

@app.route("/me/progresso-jogos", methods=["GET"])
@token_obrigatorio
def consultar_progresso_jogos():

    id_aluno = request.usuario["id"]

    try:

        resposta = supabase.table("progresso_jogos") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .execute()

        return jsonify({
            "progresso": resposta.data
        }), 200

    except Exception as erro:
        print("Erro ao consultar progresso:", erro)

        return jsonify({
            "erro": "Erro ao consultar progresso dos jogos"
        }), 500


# ==========================================
# HISTÓRICO DE PARTIDAS DO ALUNO
# ==========================================

@app.route("/partidas/<int:id_aluno>", methods=["GET"])
@token_obrigatorio
def listar_partidas(id_aluno):

    if id_aluno != request.usuario["id"]:
        return jsonify({
            "erro": "Você não pode acessar as partidas de outro aluno"
        }), 403

    try:

        resposta = supabase.table("partidas") \
            .select("*") \
            .eq("id_aluno", id_aluno) \
            .order("criado_em", desc=True) \
            .execute()

        return jsonify(resposta.data), 200

    except Exception as erro:
        print("Erro ao buscar partidas:", erro)

        return jsonify({
            "erro": "Erro ao buscar partidas"
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


# ==========================================
# REGISTRAR TENTATIVA E ENTREGAR XP
# ==========================================

@app.route("/tentativas", methods=["POST"])
@token_obrigatorio
def post_tentativa():

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Envie os dados"
        }), 400

    id_aluno = request.usuario["id"]
    id_exercicio = dados.get("id_exercicio")
    resposta_usuario = dados.get("resposta_usuario")

    if not id_exercicio or resposta_usuario is None:
        return jsonify({
            "erro": "id_exercicio e resposta_usuario são obrigatórios"
        }), 400

    if request.usuario.get("tipo_usuario") != "aluno":
        return jsonify({
            "erro": "Apenas alunos podem registrar tentativas"
        }), 403

    try:

        # Busca a resposta correta no banco
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
            str(resposta_usuario).strip().casefold()
            ==
            str(exercicio["resposta_correta"]).strip().casefold()
        )

        tipo_erro = None

        if not correta:
            tipo_erro = "Resposta incorreta"

        # Calcula o número da tentativa
        anteriores = supabase.table("tentativas") \
            .select("id") \
            .eq("id_aluno", id_aluno) \
            .eq("id_exercicio", id_exercicio) \
            .execute()

        numero_tentativa = len(anteriores.data) + 1

        # Salva a tentativa
        resposta = supabase.table("tentativas").insert({
            "id_aluno": id_aluno,
            "id_exercicio": id_exercicio,
            "resposta_usuario": str(resposta_usuario),
            "correta": correta,
            "tipo_erro": tipo_erro,
            "numero_tentativa": numero_tentativa
        }).execute()

        xp_recebido = 0

        # Entrega 10 XP somente no primeiro acerto da questão
        if correta:

            recebeu_xp = registrar_xp(
                id_aluno=id_aluno,
                quantidade=10,
                origem="questao",
                evento_chave=f"exercicio:{id_exercicio}",
                descricao="Primeiro acerto de uma questão",
                referencia_tipo="exercicio",
                referencia_id=id_exercicio
            )

            if recebeu_xp:
                xp_recebido = 10

        # Verifica se alguma conquista foi desbloqueada
        novas_conquistas = verificar_conquistas(id_aluno)

        # Soma também as recompensas das conquistas
        xp_conquistas = sum(
            item["xp_recebido"] for item in novas_conquistas
        )

        return jsonify({
            "correta": correta,
            "tipo_erro": tipo_erro,
            "xp_recebido": xp_recebido + xp_conquistas,
            "novas_conquistas": novas_conquistas
        }), 201

    except Exception as erro:
        print("Erro ao registrar tentativa:", erro)

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
# RECUPERAÇÃO
# ==========================  

@app.route("/recuperacao", methods=["POST"])
def criar_recuperacao():
    dados = request.get_json()

    if not dados:
        return jsonify({"erro": "Dados não enviados"}), 400

    try:
        resposta = supabase.table("atividades_recuperacao").insert({
            "id_aluno": dados.get("id_aluno"),
            "categoria": dados.get("categoria"),
            "motivo": dados.get("motivo"),
            "status": "pendente"
        }).execute()

        return jsonify({
            "mensagem": "Atividade de recuperação criada",
            "atividade": resposta.data
        }), 201

    except Exception as e:
        return jsonify({
            "erro": "Erro ao criar recuperação",
            "detalhes": str(e)
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