import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Evaluación Inmobiliaria Pro", layout="wide", page_icon="🏢")

# --- ESTILOS CSS ---
def local_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0E1117 !important; }
        
        /* FUENTES MÁS GRANDES (+3 aprox) */
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, label, span, div { 
            color: #FAFAFA !important; 
            font-family: 'Segoe UI', sans-serif;
            font-size: 18px !important; /* Aumentado */
        }
        
        /* Aumentar tamaño inputs */
        div[data-baseweb="input"] { 
            background-color: #262730 !important; 
            color: white !important; 
            border: 1px solid #4B5563; 
            font-size: 18px !important;
        }
        
        div.stVerticalBlock, div[data-testid="stExpander"] { background-color: #1F2937; border-radius: 12px; border: 1px solid #374151; }
        
        /* Tarjeta de intereses */
        .interest-card {
            background-color: #1F2937;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #374151;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .interest-title {
            color: #9CA3AF;
            font-size: 1.1em !important; /* Más grande */
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 15px;
        }
        
        div[data-testid="stDataFrame"] { width: 100%; font-size: 18px !important; }
        
        /* Aumentar tamaño de los KPIs (Metrics) */
        div[data-testid="stMetricValue"] {
            font-size: 34px !important; /* + grande */
        }
        div[data-testid="stMetricLabel"] {
            font-size: 18px !important;
        }

        /* Botones pequeños para el menú */
        .small-btn { margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- 1. GESTIÓN DE ESTADO ---
SCENARIOS = ["Real", "Optimista", "Pesimista"]

if 'menu_expanded' not in st.session_state:
    st.session_state.menu_expanded = False

def get_default_config(type_scen):
    # Valores base
    if type_scen == "Optimista":
        venta, tasa_uf, constr = 155000, 5.5, 68000
        inflacion, tasa_clp = 3.0, 9.0
        otros_costos_ini = 2500.0
    elif type_scen == "Pesimista":
        venta, tasa_uf, constr = 130000, 8.0, 75000
        inflacion, tasa_clp = 6.0, 14.0
        otros_costos_ini = 4000.0
    else: # Real
        venta, tasa_uf, constr = 140000, 6.5, 70000
        inflacion, tasa_clp = 4.0, 11.0
        otros_costos_ini = 3000.0
        
    return {
        # Proyecto Base
        "valor_terreno": 30000,
        "pct_fin_terreno": 60,
        "valor_contrato": constr,
        "pct_fin_construccion": 80,
        "duracion_obra": 18,
        "mes_recepcion": 22,
        "saldo_inicial_uf": 0.0,
        
        # OTROS COSTOS
        "total_otros_costos_inicial": otros_costos_ini,
        "otros_costos_mensuales": 100.0,
        
        # Deuda Bancaria
        "rango_pago_terreno": [1, 60], 
        "prioridad_terreno": False,     
        "tasa_anual_uf": tasa_uf,
        "pct_deuda_pesos": 0,     
        "tasa_anual_clp": tasa_clp, 
        "inflacion_anual": inflacion,
        "pagar_intereses_construccion": False,

        # Deuda Privada
        "prestamo_relacionada": {
            "monto": 5000.0, 
            "tasa_anual": 8.0,
            "frecuencia_pago": "Al Final",
            "mes_inicio": 1 # INICIO POR DEFECTO
        },
        "lista_kps": [
            {"nombre": "KP 1", "monto": 2000.0, "tasa_anual": 12.0, "plazo": 24, "frecuencia_pago": "Mensual", "mes_inicio": 1}
        ],
        
        "valor_venta_total": venta,
        "plan_ventas": [ 
            {"mes": 24, "pct": 20.0}, {"mes": 26, "pct": 20.0}, {"mes": 28, "pct": 20.0}, {"mes": 30, "pct": 20.0}, {"mes": 32, "pct": 20.0}
        ]
    }

if 'data_scenarios' not in st.session_state:
    st.session_state.data_scenarios = {k: get_default_config(k) for k in SCENARIOS}

# --- 2. MOTOR DE CÁLCULO ---
def calcular_flujo(data):
    # Variables Generales
    v_terr = data["valor_terreno"]
    v_cont = data["valor_contrato"]
    
    # Costos No Financieros
    v_otros_inicial = data.get("total_otros_costos_inicial", 0.0)
    v_otros_mensual = data.get("otros_costos_mensuales", 0.0)
    
    duracion = int(data["duracion_obra"])
    recepcion = int(data["mes_recepcion"])
    saldo_inicial = data.get("saldo_inicial_uf", 0)
    
    # Config Deudas
    rango_terr = data.get("rango_pago_terreno", [1, 60])
    inicio_pago_t, fin_pago_t = rango_terr[0], rango_terr[1]
    prioridad_t = data.get("prioridad_terreno", False)
    pagar_int_const = data.get("pagar_intereses_construccion", False)
    
    pct_clp = data["pct_deuda_pesos"] / 100.0
    pct_uf = 1.0 - pct_clp
    
    tasa_mensual_uf = (data["tasa_anual_uf"]/100) / 12
    tasa_mensual_clp = (data["tasa_anual_clp"]/100) / 12
    inflacion_mensual = ((1 + data["inflacion_anual"]/100)**(1/12)) - 1
    
    # --- INICIALIZACIÓN DEUDA BANCARIA ---
    pct_fin_terr = data["pct_fin_terreno"]/100
    deuda_terr_total = v_terr * pct_fin_terr
    pct_fin_const = data["pct_fin_construccion"]/100
    
    saldo_terr_uf = deuda_terr_total * pct_uf
    saldo_terr_clp_nominal = deuda_terr_total * pct_clp 
    saldo_const_uf = saldo_inicial * pct_uf
    saldo_const_clp_nominal = saldo_inicial * pct_clp 
    
    # --- INICIALIZACIÓN DEUDA PRIVADA (RELACIONADA) ---
    rel_data = data.get("prestamo_relacionada", {"monto": 0, "tasa_anual": 0, "mes_inicio": 1})
    monto_total_relacionada = rel_data["monto"]
    mes_inicio_rel = int(rel_data.get("mes_inicio", 1))
    
    # El saldo empieza en 0, a menos que el mes de inicio sea 0
    saldo_relacionada = monto_total_relacionada if mes_inicio_rel == 0 else 0.0
    
    tasa_mensual_rel = (rel_data["tasa_anual"] / 100) / 12
    frecuencia_rel = rel_data.get("frecuencia_pago", "Al Final")
    acumulado_trimestre_rel = 0
    
    # --- INICIALIZACIÓN DEUDA PRIVADA (KPs) ---
    kps_activos = []
    for kp in data.get("lista_kps", []):
        mes_ini_kp = int(kp.get("mes_inicio", 1))
        # Si el KP inicia en el mes 0, ya tiene saldo. Si no, empieza en 0.
        saldo_inicial_kp = kp["monto"] if mes_ini_kp == 0 else 0.0
        
        kps_activos.append({
            "monto_total": kp["monto"], # Monto que prestarán
            "mes_inicio": mes_ini_kp,   # Cuándo lo prestarán
            "saldo": saldo_inicial_kp,  # Saldo vivo actual
            "tasa_mensual": (kp["tasa_anual"] / 100) / 12,
            "plazo": kp["plazo"],
            "frecuencia": kp.get("frecuencia_pago", "Mensual"), 
            "acumulado_trimestre": 0, 
            "interes_acumulado_hist": 0
        })

    # Recuperos (Ventas)
    recuperos = []
    for p in data["plan_ventas"]:
        recuperos.append({"Mes": int(p["mes"]), "Monto": data["valor_venta_total"] * (p["pct"]/100)})
    
    horizonte = recepcion + 12
    if recuperos:
        horizonte = max(horizonte, max([r["Mes"] for r in recuperos]) + 6)
        
    flujo = []
    
    # --- MES 0: EQUITY INICIAL ---
    equity_terreno = v_terr * (1 - pct_fin_terr)
    inversion_inicial = equity_terreno + v_otros_inicial
    
    # Calculamos ingresos por deuda SOLAMENTE si mes_inicio == 0
    ingreso_deuda_mes_0 = 0.0
    if mes_inicio_rel == 0:
        ingreso_deuda_mes_0 += monto_total_relacionada
    for kp in kps_activos:
        if kp["mes_inicio"] == 0:
            ingreso_deuda_mes_0 += kp["monto_total"]
            
    # El flujo neto se beneficia si entra deuda en el mes 0
    flujo_neto_ini = -inversion_inicial + ingreso_deuda_mes_0

    flujo.append({
        "Mes": 0,
        "Deuda Total": (saldo_const_uf + saldo_terr_uf) + (saldo_const_clp_nominal + saldo_terr_clp_nominal) + saldo_relacionada + sum(k['saldo'] for k in kps_activos),
        "Ingresos": 0.0,
        "Ingresos Deuda": ingreso_deuda_mes_0,
        "Otros Costos (Op)": 0.0,
        "Int. Banco": 0.0, "Int. KPs": 0.0, "Int. Relac.": 0.0,
        "Devengado Banco": 0.0, "Devengado KPs": 0.0, "Devengado Relac.": 0.0,
        "Pago Intereses Total": 0.0,
        "Pago Capital": 0.0,
        "Inversión (Equity)": inversion_inicial,
        "Flujo Neto": flujo_neto_ini,
        "Flujo Acumulado": flujo_neto_ini
    })
    
    # Acumuladores KPI
    interes_acum_banco_total = 0 
    interes_acum_kps = 0
    interes_acum_relacionada = 0
    total_otros_costos_operativos = 0 
    
    factor_uf = 1.0 
    acumulado_actual = flujo_neto_ini
    mes_break_even = None
    if acumulado_actual >= 0: mes_break_even = 0
    
    for m in range(1, horizonte + 1):
        factor_uf *= (1 + inflacion_mensual)
        
        # 0. VERIFICAR TOMA DE DEUDA EN ESTE MES (KP / RELACIONADA)
        ingreso_deuda_este_mes = 0.0
        
        # A. Relacionada
        if m == mes_inicio_rel:
            saldo_relacionada += monto_total_relacionada
            ingreso_deuda_este_mes += monto_total_relacionada
            
        # B. KPs
        for kp in kps_activos:
            if m == kp["mes_inicio"]:
                kp["saldo"] += kp["monto_total"]
                ingreso_deuda_este_mes += kp["monto_total"]
        
        # 1. GENERACIÓN DE DEUDA BANCARIA (GIROS)
        egreso_equity_const = 0
        if m <= duracion:
            costo_mes_total = v_cont / duracion
            giro_banco = costo_mes_total * pct_fin_const
            egreso_equity_const = costo_mes_total - giro_banco 
            
            saldo_const_uf += giro_banco * pct_uf
            saldo_const_clp_nominal += (giro_banco * pct_clp) * factor_uf 

        # 2. CÁLCULO DE INTERESES DEL MES (DEVENGADOS SOBRE SALDO VIGENTE)
        
        # A. Banco
        int_uf_mes = (saldo_const_uf + saldo_terr_uf) * tasa_mensual_uf
        if m == 1: saldo_terr_clp_nominal *= 1.0 
        int_clp_nom_mes = (saldo_const_clp_nominal + saldo_terr_clp_nominal) * tasa_mensual_clp
        int_banco_mes_en_uf = int_uf_mes + (int_clp_nom_mes / factor_uf)
        
        saldo_const_uf += int_uf_mes
        saldo_const_clp_nominal += int_clp_nom_mes
        interes_acum_banco_total += int_banco_mes_en_uf

        # B. KPs (Interés sobre saldo actual)
        int_kps_generado_mes = 0 
        total_interes_kp_exigible_hoy = 0 
        
        for kp in kps_activos:
            if kp["saldo"] > 0: # Solo si ya se desembolsó el crédito
                ik = kp["saldo"] * kp["tasa_mensual"]
                kp["interes_acumulado_hist"] += ik
                int_kps_generado_mes += ik
                
                # Gestión Frecuencia KP
