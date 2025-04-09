from flask import Flask, jsonify, render_template, request
from algosdk.v2client import algod, indexer
from google.generativeai import GenerativeModel
from datetime import datetime
import os
from dotenv import load_dotenv
from models import asistente_financiero,clasificar_transacciones, analyze_transactions, enviar_algo_tx

load_dotenv(os.path.abspath("key.env"))
# Configuración de Algorand
wallet_address = os.getenv("ALGOWALLET")
indexer_client = indexer.IndexerClient("", "https://mainnet-idx.algonode.cloud")
algod_client = algod.AlgodClient("", "https://mainnet-api.algonode.cloud")

app = Flask(__name__)
""""
@app.route("/api")
def analisis_completo():
    resumen_textual, ingresos, gastos = clasificar_transacciones(wallet_address, limit=3)
    analisis_textual = analizar_gastos_e_ingresos(gastos, ingresos)
    balance = algod_client.account_info(wallet_address).get("amount", 0) / 1_000_000
    resumen_completo = {
        "resumen": resumen_textual,
        "analisis_financiero": analisis_textual,
        "gemini": analyze_transactions("\n".join(resumen_textual), balance)
    }
    return jsonify(resumen_completo)
"""

@app.route("/home")
def home():
    datos = asistente_financiero()

    historial = "\n".join(datos["resumen"])
    primer_mensaje = analyze_transactions(historial, datos["balance"])

    return render_template(
        'index.html',
        resumen=datos["resumen"],
        analisis=datos["analisis_financiero"],
        gemini=primer_mensaje,
        balance=datos["balance"]
    )

@app.route("/gemini-chat", methods=["POST"])
def gemini_chat():
    data = request.get_json()
    pregunta = data.get("user_input")

    resumen_textual, ingresos, gastos = clasificar_transacciones(wallet_address, limit=15)
    historial = "\n".join(resumen_textual)
    contexto = f"""
    Eres un coach financiero en la red Algorand.
    Aquí tienes el historial reciente de transacciones:

    {historial}

    El usuario pregunta:
    {pregunta}

    Responde de forma útil, breve y clara.
    """
    model = GenerativeModel('gemini-1.5-pro-latest')
    response = model.generate_content(contexto)

    return jsonify({"reply": response.text.strip()})

@app.route("/enviar-algo", methods=["POST"])
def enviar_algo():
    data = request.get_json()
    destino = data.get("destino")
    monto = float(data.get("monto"))

    return enviar_algo_tx(destino, monto)

@app.route("/api/estado")
def api_estado():
    resumen_textual, ingresos, gastos = clasificar_transacciones(wallet_address, limit=15)
    balance = algod_client.account_info(wallet_address).get("amount", 0) / 1_000_000
    return jsonify({
        "balance": round(balance, 4),
        "resumen": resumen_textual
    })


if __name__ == "__main__":
    app.run(debug=True)