import requests
import datetime
import pandas as pd
import time
import locale
# Importa o 'render_template' para servir o index.html
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


# --- OS "INGREDIENTES SECRETOS" ---
EMPRESAS = {
    "Base Importadora": {
        "client_id": "6563220445676209", "client_secret": "Ds1LzvL0VXhxQnvPU7N8LxVwLIIOn28U",
        "refresh_token": "TG-6900c87e1242ff000179d0a2-1895434949",
        "seller_id": "1895434949", "access_token": ""
    },
    "Base Almeidas": {
        "client_id": "1619895139951076", "client_secret": "ffre0g0WuDJ6f9BZ7rycixg2Na5xrn9m",
        "refresh_token": "TG-687f969242652d000121ef8a-1475523520",
        "seller_id": "1475523520", "access_token": ""
    },
    "Base Truck": {
        "client_id": "8321534892078898", "client_secret": "sERO1EikIaAWM1hVH7APtuWCXmfZz2rQ",
        "refresh_token": "TG-687a5a4b26fe5e0001367ca6-1015474523",
        "seller_id": "1015474523", "access_token": ""
    },
    "Base Peças": {
        "client_id": "3559628577694609", "client_secret": "hbSBNgcXExkJWQMQZzQgv1PoccnHuxMa",
        "refresh_token": "TG-684185656b5c170001212c64-711807406",
        "seller_id": "711807406", "access_token": ""
    },
    "Base Tech": {
        "client_id": "5881972360600603",
        "client_secret": "2rkhO1b5zB5eg8DJtp2U85UuBGCXzu1x",
        "refresh_token": "TG-6909f9cb83c19d00014c5d34-2694592690",
        "seller_id": "2694592690",
        "access_token": ""
    }
}


# --- (As suas funções refresh_access_token e process_daily_data ficam aqui, iguais) ---

def refresh_access_token(empresa_info):
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': empresa_info['client_id'],
        'client_secret': empresa_info['client_secret'],
        'refresh_token': empresa_info['refresh_token']
    }
    headers = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()['access_token']
    except requests.exceptions.RequestException as e:
        print(f"Erro ao renovar o access token: {e}")
        return None

def process_daily_data(empresa_nome, empresa_info, target_date):
    print(f"--- Processando dados de {target_date.strftime('%d/%m/%Y')} para: {empresa_nome} ---")
    access_token = refresh_access_token(empresa_info)
    if not access_token: return None
    headers = {'Authorization': f'Bearer {access_token}'}
    seller_id = empresa_info['seller_id']
    data_inicio = f"{target_date.isoformat()}T00:00:00.000-03:00"
    data_fim = f"{target_date.isoformat()}T23:59:59.999-03:00"
    all_orders = []
    offset = 0
    limit = 50
    while True:
        url_orders = (
            f"https://api.mercadolibre.com/orders/search?seller={seller_id}"
            f"&order.date_created.from={data_inicio}&order.date_created.to={data_fim}"
            f"&limit={limit}&offset={offset}"
        )
        try:
            response = requests.get(url_orders, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            all_orders.extend(data.get('results', []))
            if offset + limit >= data['paging']['total']: break
            offset += limit
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar pedidos para {empresa_nome}: {e}")
            return None
    visitas_do_dia = 0
    url_visits = f"https://api.mercadolibre.com/users/{seller_id}/items_visits?date_from={target_date.isoformat()}&date_to={target_date.isoformat()}"
    try:
        response_visits = requests.get(url_visits, headers=headers, timeout=10)
        response_visits.raise_for_status()
        visitas_do_dia = response_visits.json().get('total_visits', 0)
    except requests.exceptions.RequestException as e:
        print(f"Aviso: Não foi possível buscar as visitas para {empresa_nome}. Erro: {e}")
    total_faturamento = sum(
        p.get('transaction_amount', 0) for o in all_orders for p in o.get('payments', [])
        if p.get('status') not in ['rejected', 'refunded']
    )
    faturamento_cancelado = sum(
        p.get('transaction_amount', 0) for o in all_orders for p in o.get('payments', [])
        if p.get('status') in ['rejected', 'refunded']
    )
    buyer_ids = {o['buyer']['id'] for o in all_orders if o.get('buyer')}
    total_unidades_vendidas = sum(i.get('quantity', 0) for o in all_orders for i in o.get('order_items', []))
    quantidade_vendas = len(all_orders)
    conversao = (quantidade_vendas / visitas_do_dia * 100) if visitas_do_dia > 0 else 0
    preco_medio = total_faturamento / total_unidades_vendidas if total_unidades_vendidas > 0 else 0
    return {
        "nome": empresa_nome, "data_dados": target_date.strftime("%d/%m/%Y"),
        "faturamento": total_faturamento, "vendas": quantidade_vendas,
        "unidades": total_unidades_vendidas, "compradores": len(buyer_ids),
        "visitas": visitas_do_dia, "conversao": conversao,
        "preco_medio": preco_medio, "faturamento_cancelado": faturamento_cancelado
    }


# --- O "GARÇOM" (API de Dados) ---
@app.route('/api/dados')
def get_dashboard_data():
    print("--- PEDIDO RECEBIDO: Buscando dados frescos do ML ---")
    hoje = datetime.date.today()
    results = []
    for nome, info in EMPRESAS.items():
        dados = process_daily_data(nome, info, hoje)
        if dados:
            results.append(dados)
        time.sleep(1)
    print("--- DADOS PRONTOS: Entregando para o Salão (Frontend) ---")
    return jsonify(results)


# --- A Rota Principal (Servir o Painel) ---
@app.route('/')
def home():
    """ Esta função serve o ficheiro 'index.html' que está na pasta 'templates' """
    return render_template('index.html')


# --- O "RUN" (Ouvir em toda a rede) ---
if __name__ == "__main__":
    # O 'Render' (e outros) define a porta na variável de ambiente 'PORT'
    # Se não encontrar, usa a 5000 para testes locais.
    import os
    port = int(os.environ.get('PORT', 5000))

    print(f"Iniciando O (Servidor) em http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)
