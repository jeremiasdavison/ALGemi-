import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
from algosdk.v2client import indexer
from algosdk.v2client import algod
from collections import defaultdict
from algosdk import mnemonic, account
from algosdk.transaction import PaymentTxn
from flask import jsonify

# Load sensitive API keys from environment variables
load_dotenv(os.path.abspath("key.env"))

# Configuración de Algorand
wallet_address = os.getenv("ALGOWALLET")
indexer_client = indexer.IndexerClient("", "https://mainnet-idx.algonode.cloud")
algod_client = algod.AlgodClient("", "https://mainnet-api.algonode.cloud")

# Configurar Gemini
GENAI_API_KEY = os.getenv("GENAI_API_KEY")
genai.configure(api_key=GENAI_API_KEY)

# 🔁 Obtener últimas transacciones y clasificarlas

def clasificar_transacciones(address, limit=10):
    response = indexer_client.search_transactions_by_address(address, limit=limit)
    txns = response.get("transactions", [])
    resumen = []
    ingresos = []
    gastos = []

    for tx in txns:
        if tx.get("tx-type") != "pay":
            continue
        monto = tx.get("payment-transaction", {}).get("amount", 0) / 1_000_000
        sender = tx.get("sender")
        receiver = tx.get("payment-transaction", {}).get("receiver", "N/A")
        fecha = datetime.fromtimestamp(tx["round-time"]).strftime("%Y-%m-%d %H:%M:%S")
        linea = f"- [{fecha}] {monto:.3f} ALGO de {sender[:6]}... hacia {receiver[:6]}..."
        resumen.append(linea)
        if sender == address:
            gastos.append((receiver, monto))
        else:
            ingresos.append((sender, monto))

    return resumen, ingresos, gastos

# 📉 Analizar ingresos y gastos

def analizar_gastos_e_ingresos(gastos, ingresos):
    def sumar_por_wallet(transacciones):
        agrupado = defaultdict(float)
        for wallet, monto in transacciones:
            agrupado[wallet] += monto
        return agrupado

    resumen = ""

    if gastos:
        total_gastos = sum(m for _, m in gastos)
        promedio_gasto = total_gastos / len(gastos)
        por_wallet_gasto = sumar_por_wallet(gastos)
        resumen += f"\nGastos totales: {total_gastos:.6f} ALGO\nPromedio por gasto: {promedio_gasto:.6f} ALGO\n"
        resumen += "Destinatarios frecuentes:\n"
        for wallet, monto in por_wallet_gasto.items():
            resumen += f"  - {wallet[:6]}...: {monto:.6f} ALGO\n"
    else:
        resumen += "\nNo se registraron gastos recientes.\n"

    if ingresos:
        total_ingresos = sum(m for _, m in ingresos)
        promedio_ingreso = total_ingresos / len(ingresos)
        por_wallet_ingreso = sumar_por_wallet(ingresos)
        resumen += f"\nIngresos totales: {total_ingresos:.6f} ALGO\nPromedio por ingreso: {promedio_ingreso:.6f} ALGO\n"
        resumen += "Remitentes frecuentes:\n"
        for wallet, monto in por_wallet_ingreso.items():
            resumen += f"  - {wallet[:6]}...: {monto:.6f} ALGO\n"
    else:
        resumen += "\nNo se registraron ingresos recientes.\n"

    return resumen

# 🧠 Generar análisis con Gemini

def analyze_transactions(transactions_summary, balance_actual):
    prompt = f"""
Sos un asistente financiero para un usuario de la red Algorand.
Este es su resumen de movimientos recientes:

{transactions_summary}

El balance actual de la wallet es de {balance_actual:.2f} ALGO.

Dale un análisis simple, útil y reportero. Puede incluir:
- Sugerencias para ahorrar en fees.
- Notificación de actividad inusual.
- Consejos de gestión de fondos.

Hacelo breve así el usuario recibe la información rápido y de forma concisa.
"""
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    response = model.generate_content(prompt)
    return response.text

def ask_gemini(historial, pregunta):
    from google.generativeai import GenerativeModel
    model = GenerativeModel("gemini-pro")

    contexto = f"""
    Eres un coach financiero en la red Algorand.
    Historial de transacciones recientes:
    {historial}
    Este es el 

    El usuario pregunta:
    {pregunta}

    Responde de forma clara, útil y breve.
    """

    response = model.generate_content(contexto)
    return response

def enviar_algo_tx(destino, monto):
    try:
        seed = os.getenv("seed")
        if not seed:
            return jsonify({"success": False, "error": "No encontrado en entorno."})

        private_key = mnemonic.to_private_key(seed)
        sender = account.address_from_private_key(private_key)

        params = algod_client.suggested_params()
        amount_microalgo = int(monto * 1_000_000)

        txn = PaymentTxn(sender, params, destino, amount_microalgo)
        signed_txn = txn.sign(private_key)
        txid = algod_client.send_transaction(signed_txn)

        fee = params.min_fee / 1_000_000

        explorer_url = f"https://algoexplorer.io/tx/{txid}"
        return jsonify({"success": True, "txid": txid, "fee": fee, "explorer": explorer_url})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})



def asistente_financiero():
    resumen_textual, ingresos, gastos = clasificar_transacciones(wallet_address, limit=15)
    info_gastos_ingresos = analizar_gastos_e_ingresos(gastos, ingresos)

    account_info = algod_client.account_info(wallet_address)
    balance = account_info.get("amount", 0) / 1_000_000

    #gemini_text = analyze_transactions("".join(resumen_textual), balance)

    return {
        "balance": round(balance, 4),
        "resumen": resumen_textual,
        "analisis_financiero": info_gastos_ingresos,
        #"gemini": gemini_text
    }
#asistente_financiero()