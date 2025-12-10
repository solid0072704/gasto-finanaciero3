import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Evaluación Inmobiliaria Pro", layout="wide", page_icon="🏢")

# --- 0. LIMPIEZA DE CACHÉ AUTOMÁTICA ---
if 'data_scenarios' in st.session_state:
    try:
        # Verificamos si existe la nueva clave en el diccionario
        test_key = st.session_state.data_scenarios["Real"].get("pct_avance_inicial")
        if test_key is None: 
            raise KeyError
    except KeyError:
        st.session_state.clear()
        st.rerun()

# --- ESTILOS CSS ---
def local_css():
    st.markdown("""
    <style>
        .stApp { background-color: #0E1117 !important; }
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, label, span, div { 
            color: #FAFAFA !important; 
            font-family: 'Segoe UI', sans-serif;
            font-size: 18px !important; 
        }
        div[data-baseweb="input"] { 
            background-color: #262730 !important; 
            color: white !important; 
            border: 1px solid #4B5563; 
            font-size: 18px !important;
        }
        div.stVerticalBlock, div[data-testid="stExpander"] { background-color: #1F2937; border-radius: 12px; border: 1px solid #374151; }
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
            font-size: 1.1em !important; 
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 15px;
        }
        div[data-testid="stDataFrame"] { width: 100%; font-size: 18px !important; }
        div[data-testid="stMetricValue"] { font-size: 34px !important; }
        div[data-testid="stMetricLabel"] { font-size: 18px !important; }
        .small-btn { margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- 1. GESTIÓN DE ESTADO ---
SCENARIOS = ["Real", "Optimista", "Pesimista"]

if 'menu_expanded' not in st.session_state:
    st.session_state.menu_expanded = False

if 'exp_reset_token' not in st.session_state:
    st.session_state.exp_reset_token = 0

def get_default_config(type_scen):
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
        "valor_terreno": 30000,
        "pct_fin_terreno": 60,
        "valor_contrato": constr,
        "pct_fin_construccion": 80,
        "duracion_obra": 18,
        "mes_inicio_obra": 1,
        
        # PARAMETRO: % del contrato que se gasta el mes 1
        "pct_avance_inicial": 20.0, 
        
        "mes_recepcion": 22,
        
        "saldo_inicial_uf": 0.0, # Deuda Viva
        "intereses_previos_uf": 0.0, # Sunk Cost
        
        "total_otros_costos_inicial": otros_costos_ini,
        "otros_costos_mensuales": 100.0,
        
        "rango_pago_terreno": [1, 60], 
        "prioridad_terreno": False,      
        "tasa_anual_uf": tasa_uf,
        "pct_deuda_pesos": 0,      
        "tasa_anual_clp": tasa_clp, 
        "inflacion_anual": inflacion,
        "pagar_intereses_construccion": False,

        "lista_relacionadas": [
             {"nombre": "Relac. 1", "monto": 5000.0, "tasa_anual": 8.0, "frecuencia_pago": "Al Final", "mes_inicio": 1}
        ],
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
    
    # Cronograma
    duracion = int(data["duracion_obra"])
    inicio_obra = int(data.get("mes_inicio_obra", 1)) 
    
    # Recuperamos el porcentaje inicial definido por el usuario (default 20%)
    pct_avance_inicial = data.get("pct_avance_inicial", 20.0) / 100.0
    
    recepcion = int(data["mes_recepcion"])
    fin_obra = inicio_obra + duracion - 1
    
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
    
    # --- INICIALIZACIÓN DEUDA PRIVADA ---
    rel_activos = []
    for rel in data.get("lista_relacionadas", []):
        mes_ini_rel = int(rel.get("mes_inicio", 1))
        saldo_inicial_rel = rel["monto"] if mes_ini_rel == 0 else 0.0
        rel_activos.append({
            "monto_total": rel["monto"], "mes_inicio": mes_ini_rel, "saldo": saldo_inicial_rel,
            "tasa_mensual": (rel["tasa_anual"] / 100) / 12, "frecuencia": rel.get("frecuencia_pago", "Al Final"), "acumulado_trimestre": 0
        })

    kps_activos = []
    for kp in data.get("lista_kps", []):
        mes_ini_kp = int(kp.get("mes_inicio", 1))
        saldo_inicial_kp = kp["monto"] if mes_ini_kp == 0 else 0.0
        kps_activos.append({
            "monto_total": kp["monto"], "mes_inicio": mes_ini_kp, "saldo": saldo_inicial_kp,
            "tasa_mensual": (kp["tasa_anual"] / 100) / 12, "plazo": kp["plazo"],
            "frecuencia": kp.get("frecuencia_pago", "Mensual"), "acumulado_trimestre": 0, "interes_acumulado_hist": 0
        })

    # Recuperos y Horizonte
    recuperos = []
    meses_con_venta = []
    for p in data["plan_ventas"]:
        recuperos.append({"Mes": int(p["mes"]), "Monto": data["valor_venta_total"] * (p["pct"]/100)})
        if p["pct"] > 0: meses_con_venta.append(int(p["mes"]))
    
    # IDENTIFICAR EL ÚLTIMO MES DE VENTA (PARA FORZAR PAGO)
    ultimo_mes_venta = max(meses_con_venta) if meses_con_venta else -1
    
    horizonte = recepcion + 12
    if recuperos:
        horizonte = max(horizonte, max([r["Mes"] for r in recuperos]) + 6)
    horizonte = max(horizonte, fin_obra + 6)
        
    flujo = []
    
    # --- MES 0 ---
    equity_terreno = v_terr * (1 - pct_fin_terr)
    inversion_inicial = equity_terreno + v_otros_inicial
    ingreso_deuda_mes_0 = 0.0
    for kp in kps_activos:
        if kp["mes_inicio"] == 0: ingreso_deuda_mes_0 += kp["monto_total"]
    for rel in rel_activos:
        if rel["mes_inicio"] == 0: ingreso_deuda_mes_0 += rel["monto_total"]
            
    flujo_neto_ini = -inversion_inicial + ingreso_deuda_mes_0
    saldo_total_rel = sum(r['saldo'] for r in rel_activos)
    saldo_total_kps = sum(k['saldo'] for k in kps_activos)

    flujo.append({
        "Mes": 0,
        "Deuda Total": (saldo_const_uf + saldo_terr_uf) + (saldo_const_clp_nominal + saldo_terr_clp_nominal) + saldo_total_rel + saldo_total_kps,
        "Ingresos": 0.0, "Ingresos Deuda": ingreso_deuda_mes_0, "Otros Costos (Op)": 0.0,
        "Int. Banco": 0.0, "Int. KPs": 0.0, 
        "Int. Relac.": 0.0, # IMPORTANTE: Nombre con punto al final
        "Devengado Banco": 0.0, "Devengado KPs": 0.0, "Devengado Relac.": 0.0,
        "Pago Intereses Total": 0.0, "Pago Capital": 0.0,
        "Inversión (Equity)": inversion_inicial, "Flujo Neto": flujo_neto_ini, "Flujo Acumulado": flujo_neto_ini
    })
    
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
        
        # 0. DEUDA PRIVADA ENTRADA
        ingreso_deuda_este_mes = 0.0
        for rel in rel_activos:
            if m == rel["mes_inicio"]:
                rel["saldo"] += rel["monto_total"]
                ingreso_deuda_este_mes += rel["monto_total"]
        for kp in kps_activos:
            if m == kp["mes_inicio"]:
                kp["saldo"] += kp["monto_total"]
                ingreso_deuda_este_mes += kp["monto_total"]
        
        # 1. GENERACIÓN DE DEUDA BANCARIA (GIROS)
        # === LÓGICA DE DISTRIBUCIÓN COSTO CONSTRUCCIÓN ===
        egreso_equity_const = 0
        
        if m >= inicio_obra and m <= fin_obra:
            if m == inicio_obra:
                if duracion == 1:
                     costo_mes_total = v_cont
                else:
                     costo_mes_total = v_cont * pct_avance_inicial
            else:
                pct_restante = 1.0 - pct_avance_inicial
                remanente = v_cont * pct_restante
                meses_restantes = duracion - 1
                costo_mes_total = remanente / meses_restantes if meses_restantes > 0 else 0
            
            giro_banco = costo_mes_total * pct_fin_const
            egreso_equity_const = costo_mes_total - giro_banco 
            saldo_const_uf += giro_banco * pct_uf
            saldo_const_clp_nominal += (giro_banco * pct_clp) * factor_uf 

        # 2. INTERESES DEVENGADOS
        # A. Banco
        int_uf_mes = (saldo_const_uf + saldo_terr_uf) * tasa_mensual_uf
        if m == 1: saldo_terr_clp_nominal *= 1.0 
        int_clp_nom_mes = (saldo_const_clp_nominal + saldo_terr_clp_nominal) * tasa_mensual_clp
        int_banco_mes_en_uf = int_uf_mes + (int_clp_nom_mes / factor_uf)
        saldo_const_uf += int_uf_mes
        saldo_const_clp_nominal += int_clp_nom_mes
        interes_acum_banco_total += int_banco_mes_en_uf

        # B. KPs
        int_kps_generado_mes = 0 
        total_interes_kp_exigible_hoy = 0 
        for kp in kps_activos:
            if kp["saldo"] > 0:
                ik = kp["saldo"] * kp["tasa_mensual"]
                kp["interes_acumulado_hist"] += ik
                int_kps_generado_mes += ik
                interes_exigible_este_kp = 0
                if kp["frecuencia"] == "Mensual":
                    kp["saldo"] += ik
                    interes_exigible_este_kp = ik
                elif kp["frecuencia"] == "Trimestral":
                    kp["saldo"] += ik
                    kp["acumulado_trimestre"] += ik
                    if m % 3 == 0:
                        interes_exigible_este_kp = kp["acumulado_trimestre"]
                        kp["acumulado_trimestre"] = 0 
                elif kp["frecuencia"] == "Al Final":
                    kp["saldo"] += ik
                total_interes_kp_exigible_hoy += interes_exigible_este_kp
        interes_acum_kps += int_kps_generado_mes
        
        # C. Relacionada
        int_rel_mes = 0
        total_interes_rel_exigible_hoy = 0
        for rel in rel_activos:
            if rel["saldo"] > 0:
                ir = rel["saldo"] * rel["tasa_mensual"]
                int_rel_mes += ir
                interes_exigible_este_rel = 0
                if rel["frecuencia"] == "Mensual":
                    rel["saldo"] += ir
                    interes_exigible_este_rel = ir
                elif rel["frecuencia"] == "Trimestral":
                    rel["saldo"] += ir
                    rel["acumulado_trimestre"] += ir
                    if m % 3 == 0:
                        interes_exigible_este_rel = rel["acumulado_trimestre"]
                        rel["acumulado_trimestre"] = 0
                else: 
                    rel["saldo"] += ir
                total_interes_rel_exigible_hoy += interes_exigible_este_rel
        interes_acum_relacionada += int_rel_mes
        
        # 3. FLUJO OPERATIVO
        ingreso_uf = sum([r["Monto"] for r in recuperos if r["Mes"] == m])
        gasto_operativo_mes = v_otros_mensual if (m <= recepcion + 6) else 0 
        total_otros_costos_operativos += gasto_operativo_mes
        
        flujo_operativo = ingreso_uf + ingreso_deuda_este_mes - gasto_operativo_mes
        dinero_para_deuda = max(0.0, flujo_operativo)
        
        # --- LÓGICA DE PAGO OBLIGATORIO DE INTERESES (EQUITY) ---
        if pagar_int_const:
            if dinero_para_deuda < int_banco_mes_en_uf:
                deficit = int_banco_mes_en_uf - dinero_para_deuda
                dinero_para_deuda += deficit 
                egreso_equity_const += deficit 
        
        # 4. WATERFALL DE PAGOS (CON LOGICA DE CIERRE FORZADO)
        
        # --- CHECK DE CIERRE: ¿ES EL ÚLTIMO MES DE VENTAS? ---
        es_mes_cierre = (m == ultimo_mes_venta)
        
        # --- A. BANCO ---
        real_const_uf = saldo_const_uf + (saldo_const_clp_nominal / factor_uf)
        real_terr_uf = saldo_terr_uf + (saldo_terr_clp_nominal / factor_uf)
        deuda_banco_total = real_const_uf + real_terr_uf
        
        pago_banco_total = 0
        pago_banco_interes = 0
        pago_banco_capital = 0

        if deuda_banco_total > 0:
            # SI ES MES DE CIERRE, PAGAMOS TODO AUNQUE NO HAYA CAJA (EQUITY)
            if es_mes_cierre:
                monto_a_pagar_banco = deuda_banco_total
            else:
                monto_a_pagar_banco = min(deuda_banco_total, dinero_para_deuda) if dinero_para_deuda > 0 else 0
            
            if monto_a_pagar_banco > 0:
                pago_banco_interes = min(monto_a_pagar_banco, int_banco_mes_en_uf)
                
                if pagar_int_const and pago_banco_interes < int_banco_mes_en_uf and monto_a_pagar_banco >= int_banco_mes_en_uf:
                    pago_banco_interes = int_banco_mes_en_uf

                pago_banco_capital = monto_a_pagar_banco - pago_banco_interes
                
                es_rango_terreno = (m >= inicio_pago_t and m <= fin_pago_t)
                p_terr, p_const = 0, 0
                
                if es_rango_terreno:
                    if prioridad_t:
                        p_terr = min(real_terr_uf, monto_a_pagar_banco)
                        p_const = min(real_const_uf, monto_a_pagar_banco - p_terr)
                    else:
                        if deuda_banco_total > 0:
                            p_terr = monto_a_pagar_banco * (real_terr_uf / deuda_banco_total)
                            p_const = monto_a_pagar_banco * (real_const_uf / deuda_banco_total)
                else:
                    p_const = min(real_const_uf, monto_a_pagar_banco)
                
                # Descontar Saldos
                if p_terr > 0 and real_terr_uf > 0:
                    prop = p_terr / real_terr_uf
                    # Ajuste fino para evitar decimales residuales en cierre
                    if es_mes_cierre and p_terr >= real_terr_uf - 0.1: 
                         saldo_terr_uf = 0
                         saldo_terr_clp_nominal = 0
                    else:
                        saldo_terr_uf -= (saldo_terr_uf * prop)
                        saldo_terr_clp_nominal -= (saldo_terr_clp_nominal * prop)

                if p_const > 0 and real_const_uf > 0:
                    prop = p_const / real_const_uf
                    if es_mes_cierre and p_const >= real_const_uf - 0.1:
                        saldo_const_uf = 0
                        saldo_const_clp_nominal = 0
                    else:
                        saldo_const_uf -= (saldo_const_uf * prop)
                        saldo_const_clp_nominal -= (saldo_const_clp_nominal * prop)
                
                pago_banco_total = monto_a_pagar_banco
                dinero_para_deuda -= pago_banco_total # Puede quedar negativo si es cierre forzado

        # --- B. KPs ---
        pago_kps_total = 0
        pago_kps_interes = 0
        saldo_total_kps_contable = sum(k['saldo'] for k in kps_activos)
        
        if saldo_total_kps_contable > 0:
            if es_mes_cierre:
                # Pagamos todo
                monto_total_kp_pagar = saldo_total_kps_contable
                pago_kps_interes = 0 
                pago_kps_total = monto_total_kp_pagar
                for kp in kps_activos: kp["saldo"] = 0
                dinero_para_deuda -= pago_kps_total
            
            elif dinero_para_deuda > 0:
                monto_interes_kp_pagar = min(dinero_para_deuda, total_interes_kp_exigible_hoy)
                for kp in kps_activos:
                    exigible_kp = 0
                    if kp["frecuencia"] == "Mensual": exigible_kp = (kp["saldo"] * kp["tasa_mensual"])
                    elif kp["frecuencia"] == "Trimestral" and m % 3 == 0: exigible_kp = kp["acumulado_trimestre"]
                    
                    if total_interes_kp_exigible_hoy > 0:
                        peso_int = exigible_kp / total_interes_kp_exigible_hoy
                        pago_i = monto_interes_kp_pagar * peso_int
                        kp["saldo"] -= pago_i
                pago_kps_interes = monto_interes_kp_pagar
                dinero_para_deuda -= pago_kps_interes
                
                if dinero_para_deuda > 0:
                    monto_capital_kp = min(dinero_para_deuda, sum(k['saldo'] for k in kps_activos))
                    pago_kps_total = pago_kps_interes + monto_capital_kp
                    saldo_kps_actual = sum(k['saldo'] for k in kps_activos)
                    for kp in kps_activos:
                        if saldo_kps_actual > 0:
                            peso = kp["saldo"] / saldo_kps_actual
                            abono = monto_capital_kp * peso
                            kp["saldo"] -= abono
                    dinero_para_deuda -= monto_capital_kp
                else:
                    pago_kps_total = pago_kps_interes

        # --- C. Relacionada ---
        pago_rel_total = 0
        pago_rel_interes = 0
        saldo_total_rel_contable = sum(r['saldo'] for r in rel_activos)
        
        if saldo_total_rel_contable > 0:
            if es_mes_cierre:
                monto_total_rel_pagar = saldo_total_rel_contable
                pago_rel_total = monto_total_rel_pagar
                for rel in rel_activos: rel["saldo"] = 0
                dinero_para_deuda -= pago_rel_total
            
            elif dinero_para_deuda > 0:
                monto_interes_rel_pagar = min(dinero_para_deuda, total_interes_rel_exigible_hoy)
                for rel in rel_activos:
                    exigible_rel = 0
                    if rel["frecuencia"] == "Mensual": exigible_rel = (rel["saldo"] * rel["tasa_mensual"])
                    elif rel["frecuencia"] == "Trimestral" and m % 3 == 0: exigible_rel = rel["acumulado_trimestre"]
                    
                    if total_interes_rel_exigible_hoy > 0:
                        peso_int = exigible_rel / total_interes_rel_exigible_hoy
                        pago_i = monto_interes_rel_pagar * peso_int
                        rel["saldo"] -= pago_i
                pago_rel_interes = monto_interes_rel_pagar
                dinero_para_deuda -= pago_rel_interes
                
                if dinero_para_deuda > 0:
                    monto_capital_rel = min(dinero_para_deuda, sum(r['saldo'] for r in rel_activos))
                    pago_rel_total = pago_rel_interes + monto_capital_rel
                    saldo_rel_actual = sum(r['saldo'] for r in rel_activos)
                    for rel in rel_activos:
                        if saldo_rel_actual > 0:
                            peso = rel["saldo"] / saldo_rel_actual
                            abono = monto_capital_rel * peso
                            rel["saldo"] -= abono
                    dinero_para_deuda -= monto_capital_rel
                else:
                    pago_rel_total = pago_rel_interes

        # --- RESULTADOS ---
        total_pagado_intereses = pago_banco_interes + pago_kps_interes + pago_rel_interes
        total_pagado_capital = (pago_banco_total + pago_kps_total + pago_rel_total) - total_pagado_intereses
        
        flujo_neto_mes = dinero_para_deuda - egreso_equity_const 
        if flujo_operativo < 0:
            flujo_neto_mes = flujo_operativo - egreso_equity_const

        acumulado_actual += flujo_neto_mes
        saldo_kps_reporte = sum([k["saldo"] for k in kps_activos])
        saldo_rel_reporte = sum([r["saldo"] for r in rel_activos])
        
        if acumulado_actual >= 0 and mes_break_even is None:
            mes_break_even = m

        deuda_banco_reporte = (saldo_const_uf + saldo_terr_uf) + ((saldo_const_clp_nominal + saldo_terr_clp_nominal) / factor_uf)

        flujo.append({
            "Mes": m,
            "Deuda Banco": deuda_banco_reporte,
            "Deuda KPs": saldo_kps_reporte,
            "Deuda Relac.": saldo_rel_reporte,
            "Deuda Total": deuda_banco_reporte + saldo_kps_reporte + saldo_rel_reporte,
            "Ingresos": ingreso_uf,
            "Ingresos Deuda": ingreso_deuda_este_mes, 
            "Otros Costos (Op)": gasto_operativo_mes,
            "Inversión (Equity)": egreso_equity_const,
            
            "Int. Banco": pago_banco_interes,
            "Int. KPs": pago_kps_interes,
            "Int. Relac.": pago_rel_interes, # AQUI ESTABA EL ERROR (Faltaba punto) - CORREGIDO
            
            "Devengado Banco": int_banco_mes_en_uf,
            "Devengado KPs": int_kps_generado_mes,
            "Devengado Relac.": int_rel_mes,
            
            "Pago Intereses Total": total_pagado_intereses,
            "Pago Capital": total_pagado_capital,
            "Flujo Neto": flujo_neto_mes,
            "Flujo Acumulado": acumulado_actual
        })
    
    df = pd.DataFrame(flujo)
    
    costo_fin_total = interes_acum_banco_total + interes_acum_kps + interes_acum_relacionada
    costo_proyecto_total = v_terr + v_cont + v_otros_inicial + total_otros_costos_operativos + costo_fin_total
    utilidad = data["valor_venta_total"] - costo_proyecto_total
    
    roi = (utilidad / costo_proyecto_total) * 100 if costo_proyecto_total > 0 else 0

    return {
        "df": df,
        "utilidad": utilidad,
        "costo_financiero_total": costo_fin_total,
        "detalles_fin": {
            "banco": interes_acum_banco_total,
            "kps": interes_acum_kps,
            "relacionada": interes_acum_relacionada
        },
        "roi": roi,
        "peak_deuda": df["Deuda Total"].max(),
        "break_even": mes_break_even
    }

# --- 3. UI ---
st.title("📊 Análisis Gasto financiero proyectos inmobiliarios")

col_inputs, col_dash = st.columns([1.3, 2.7], gap="medium")

if 'calc_results' not in st.session_state:
    st.session_state.calc_results = {name: calcular_flujo(st.session_state.data_scenarios[name]) for name in SCENARIOS}

with col_inputs:
    st.markdown("### Configuración")
    
    col_btn1, col_btn2 = st.columns(2)
    
    if col_btn1.button("🔽 Expandir Todo", key="btn_expand", use_container_width=True):
        st.session_state.menu_expanded = True
        st.session_state.exp_reset_token += 1 
        st.rerun()
        
    if col_btn2.button("🔼 Colapsar Todo", key="btn_collapse", use_container_width=True):
        st.session_state.menu_expanded = False
        st.session_state.exp_reset_token += 1 
        st.rerun()
    
    if st.button("🚀 Procesar y Actualizar", type="primary", use_container_width=True):
        st.session_state.calc_results = {name: calcular_flujo(st.session_state.data_scenarios[name]) for name in SCENARIOS}
        st.rerun()
    
    tabs = st.tabs(["🟦 Real", "🟩 Optimista", "🟥 Pesimista"])
    
    def render_scenario_inputs(scen_key):
        data = st.session_state.data_scenarios[scen_key]
        is_expanded = st.session_state.menu_expanded
        lbl_suffix = "\u200b" * st.session_state.exp_reset_token
        
        with st.container():
            with st.expander(f"🏗️ Proyecto Base & Costos{lbl_suffix}", expanded=is_expanded):
                data["valor_terreno"] = st.number_input("Valor Terreno (UF)", value=data["valor_terreno"], key=f"{scen_key}_vt")
                data["pct_fin_terreno"] = st.slider("% Fin. Terreno", 0, 100, data["pct_fin_terreno"], key=f"{scen_key}_fin_t")
                data["valor_contrato"] = st.number_input("Costo Const. (UF)", value=data["valor_contrato"], key=f"{scen_key}_vc")
                data["pct_fin_construccion"] = st.slider("% Fin. Construcción", 0, 100, data["pct_fin_construccion"], key=f"{scen_key}_fin_c")
                data["pct_avance_inicial"] = st.slider("% Avance 1er Mes (Giro Inicial)", 0.0, 100.0, float(data.get("pct_avance_inicial", 20.0)), key=f"{scen_key}_pinit")
                
                c_obra, c_ini, c_recep = st.columns(3)
                data["duracion_obra"] = c_obra.number_input("Meses Obra", value=data["duracion_obra"], key=f"{scen_key}_dur")
                data["mes_inicio_obra"] = c_ini.number_input("Mes Inicio Obra (Gantt)", value=data.get("mes_inicio_obra", 1), key=f"{scen_key}_ini_obra")
                data["mes_recepcion"] = c_recep.number_input("Mes Recepción Final", value=data["mes_recepcion"], key=f"{scen_key}_recep")
                
                st.markdown("---")
                st.caption("🏦 Estado Situación Inicial")
                c_sald1, c_sald2 = st.columns(2)
                data["saldo_inicial_uf"] = c_sald1.number_input("Deuda Inicial (Capital Vivo)", value=data.get("saldo_inicial_uf", 0.0), help="Deuda vigente al mes 0. ESTO GENERA INTERESES.", key=f"{scen_key}_ini")
                data["intereses_previos_uf"] = c_sald2.number_input("Intereses Ya Pagados (Histórico)", value=data.get("intereses_previos_uf", 0.0), help="Intereses pagados antes de este flujo. Solo suma al costo total.", key=f"{scen_key}_int_prev")
                
                st.markdown("---")
                st.caption("📋 Otros Costos No Financieros")
                data["total_otros_costos_inicial"] = st.number_input("Otros Costos Iniciales (Permisos, Arq)", value=data.get("total_otros_costos_inicial", 0.0), key=f"{scen_key}_oci")
                data["otros_costos_mensuales"] = st.number_input("Gasto Operativo Mensual (Admin, Ventas)", value=data.get("otros_costos_mensuales", 0.0), key=f"{scen_key}_ocm")

            with st.expander(f"🏦 Deuda Bancaria{lbl_suffix}", expanded=is_expanded):
                data["pct_deuda_pesos"] = st.slider("% Deuda CLP", 0, 100, data["pct_deuda_pesos"], key=f"{scen_key}_mix")
                
                c1, c2, c3 = st.columns(3)
                data["tasa_anual_uf"] = c1.number_input("Tasa UF", value=data["tasa_anual_uf"], step=0.1, key=f"{scen_key}_tuf")
                data["tasa_anual_clp"] = c2.number_input("Tasa CLP", value=data["tasa_anual_clp"], step=0.1, key=f"{scen_key}_tclp")
                data["inflacion_anual"] = c3.number_input("Infl. %", value=data["inflacion_anual"], step=0.1, key=f"{scen_key}_inf")
                
                data["pagar_intereses_construccion"] = st.checkbox("Pagar intereses durante construcción (Equity)", value=data.get("pagar_intereses_construccion", False), key=f"{scen_key}_pay_int")
                
                st.markdown("**Pago Terreno**")
                rango_val = data.get("rango_pago_terreno", [1, 60])
                data["rango_pago_terreno"] = st.slider("Ventana Pago", 1, 60, (rango_val[0], rango_val[1]), key=f"{scen_key}_rng")
                data["prioridad_terreno"] = st.checkbox("Prioridad Terreno", value=data.get("prioridad_terreno", False), key=f"{scen_key}_prio")

            with st.expander(f"🤝 Deuda Privada (KPs y Relac.){lbl_suffix}", expanded=is_expanded):
                st.markdown("##### Préstamo Relacionada")
                if st.button("➕ Agregar Deuda Relacionada", key=f"add_rel_{scen_key}"):
                    data["lista_relacionadas"].append({"nombre": f"Rel {len(data.get('lista_relacionadas', []))+1}", "monto": 5000.0, "tasa_anual": 8.0, "frecuencia_pago": "Al Final", "mes_inicio": 1})
                    st.rerun()

                idx_rel_remove = []
                for i, rel in enumerate(data.get("lista_relacionadas", [])):
                    st.markdown(f"**Relacionada #{i+1}**")
                    r1, r2, r3 = st.columns(3)
                    rel["monto"] = r1.number_input("Monto", value=float(rel["monto"]), key=f"rm_{scen_key}_{i}")
                    rel["tasa_anual"] = r2.number_input("Tasa %", value=float(rel["tasa_anual"]), step=0.1, key=f"rt_{scen_key}_{i}")
                    rel["mes_inicio"] = r3.number_input("Mes Inicio", value=int(rel.get("mes_inicio", 1)), key=f"rini_{scen_key}_{i}")
                    r4, r5 = st.columns([2, 1])
                    rel["frecuencia_pago"] = r4.selectbox("Pago Interés", ["Mensual", "Trimestral", "Al Final"], index=["Mensual", "Trimestral", "Al Final"].index(rel.get("frecuencia_pago", "Al Final")), key=f"rf_{scen_key}_{i}")
                    if r5.button("🗑️", key=f"del_rel_{scen_key}_{i}"): idx_rel_remove.append(i)
                    st.divider()
                if idx_rel_remove:
                    for i in sorted(idx_rel_remove, reverse=True): data["lista_relacionadas"].pop(i)
                    st.rerun()

                st.markdown("---")
                st.markdown("##### Inversionistas (KPs)")
                if st.button("➕ Agregar KP", key=f"add_kp_{scen_key}"):
                    data["lista_kps"].append({"nombre": f"KP {len(data['lista_kps'])+1}", "monto": 1000.0, "tasa_anual": 10.0, "plazo": 24, "frecuencia_pago": "Mensual", "mes_inicio": 1})
                    st.rerun()

                idx_kp_remove = []
                for i, kp in enumerate(data["lista_kps"]):
                    st.markdown(f"**KP #{i+1}**")
                    k1, k2, k3 = st.columns(3)
                    kp["monto"] = k1.number_input("Monto", value=float(kp["monto"]), key=f"kpm_{scen_key}_{i}")
                    kp["tasa_anual"] = k2.number_input("Tasa %", value=float(kp["tasa_anual"]), step=0.1, key=f"kpt_{scen_key}_{i}")
                    kp["mes_inicio"] = k3.number_input("Mes Inicio", value=int(kp.get("mes_inicio", 1)), key=f"kpini_{scen_key}_{i}") 
                    k4, k5 = st.columns([2, 1])
                    kp["plazo"] = k4.number_input("Plazo", value=int(kp["plazo"]), key=f"kpp_{scen_key}_{i}")
                    kp["frecuencia_pago"] = k4.selectbox("Pago Interés", ["Mensual", "Trimestral", "Al Final"], index=["Mensual", "Trimestral", "Al Final"].index(kp.get("frecuencia_pago", "Mensual")), key=f"kpf_{scen_key}_{i}")
                    if k5.button("🗑️", key=f"del_kp_{scen_key}_{i}"): idx_kp_remove.append(i)
                    st.divider()
                if idx_kp_remove:
                    for i in sorted(idx_kp_remove, reverse=True): data["lista_kps"].pop(i)
                    st.rerun()

            with st.expander(f"💰 Plan de Ventas{lbl_suffix}", expanded=is_expanded):
                data["valor_venta_total"] = st.number_input("Venta Total (UF)", value=data["valor_venta_total"], key=f"{scen_key}_vvt")
                lista_ventas = data["plan_ventas"]
                total_pct = sum([item["pct"] for item in lista_ventas])
                col_bar, col_txt = st.columns([3, 1])
                col_bar.progress(min(total_pct / 100.0, 1.0))
                col_txt.markdown(f"**{total_pct:.1f}%**")
                
                if st.button("➕ Hito Venta", key=f"add_v_{scen_key}"):
                    last_mes = lista_ventas[-1]["mes"] if lista_ventas else 23
                    data["plan_ventas"].append({"mes": last_mes + 1, "pct": max(0.0, 100.0 - total_pct)})
                    st.rerun()
                idx_v_rem = []
                for i, r in enumerate(lista_ventas):
                    c1, c2, c3 = st.columns([1.5, 1.5, 0.5])
                    r["mes"] = c1.number_input("Mes", value=int(r["mes"]), key=f"vm_{scen_key}_{i}", label_visibility="collapsed")
                    r["pct"] = c2.number_input("%", value=float(r["pct"]), key=f"vp_{scen_key}_{i}", label_visibility="collapsed")
                    if c3.button("x", key=f"del_v_{scen_key}_{i}"): idx_v_rem.append(i)
                if idx_v_rem:
                    for i in sorted(idx_v_rem, reverse=True): data["plan_ventas"].pop(i)
                    st.rerun()

    with tabs[0]: render_scenario_inputs("Real")
    with tabs[1]: render_scenario_inputs("Optimista")
    with tabs[2]: render_scenario_inputs("Pesimista")

# --- CALCULO AUTOMÁTICO ---
results = {name: calcular_flujo(st.session_state.data_scenarios[name]) for name in SCENARIOS}
res = results["Real"]
fmt_nums = lambda x: f"{x:,.0f}".replace(",", ".")

with col_dash:
    st.markdown("### 🏆 KPIs Escenario Real")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Utilidad", f"{res['utilidad']:,.0f} UF")
    k2.metric("ROI Proyecto", f"{res['roi']:.1f}%")
    k3.metric("Mes flujo positivo", f"Mes {res['break_even']}" if res['break_even'] else "N/A")
    k4.metric("Peak Deuda", f"{res['peak_deuda']:,.0f} UF")

    # --- TARJETA DE INTERESES ---
    st.markdown("#### 💳 Costos Financieros Totales")
    int_previos = st.session_state.data_scenarios["Real"].get("intereses_previos_uf", 0.0)
    total_fin_global = res['costo_financiero_total'] + int_previos
    
    with st.container():
        st.markdown('<div class="interest-card">', unsafe_allow_html=True)
        st.markdown('<div class="interest-title">Desglose Global (Simulación + Histórico)</div>', unsafe_allow_html=True)
        det = res["detalles_fin"]
        ic1, ic2, ic3, ic4 = st.columns(4)
        ic1.metric("🏦 Banco (Futuro)", f"{det['banco']:,.0f} UF")
        ic2.metric("⏮️ Int. Previos", f"{int_previos:,.0f} UF", help="Intereses pagados antes del inicio de la simulación")
        ic3.metric("🤝 Privados (KPs/Rel)", f"{det['kps'] + det['relacionada']:,.0f} UF")
        ic4.metric("💰 COSTO TOTAL", f"{total_fin_global:,.0f} UF", delta="Final del Proyecto")
        st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("📋 Tabla Detallada (Verificación de Pagos)", expanded=False):
        cols_show = ["Mes", "Ingresos", "Ingresos Deuda", "Otros Costos (Op)", "Int. Banco", "Int. KPs", "Int. Relac.", "Pago Capital", "Flujo Neto", "Flujo Acumulado", "Deuda Total"]
        df_display = res["df"][cols_show].copy()
        df_display["Mes"] = df_display["Mes"].astype(str)
        total_row = {
            "Mes": "TOTAL",
            "Ingresos": df_display["Ingresos"].sum(),
            "Ingresos Deuda": df_display["Ingresos Deuda"].sum(), 
            "Otros Costos (Op)": df_display["Otros Costos (Op)"].sum(),
            "Int. Banco": df_display["Int. Banco"].sum(),
            "Int. KPs": df_display["Int. KPs"].sum(),
            "Int. Relac.": df_display["Int. Relac."].sum(), # CON PUNTO
            "Pago Capital": df_display["Pago Capital"].sum(),
            "Flujo Neto": df_display["Flujo Neto"].sum(),
            "Flujo Acumulado": df_display["Flujo Neto"].sum(), 
            "Deuda Total": 0.0 
        }
        df_final = pd.concat([df_display, pd.DataFrame([total_row])], ignore_index=True)
        cols_nums = ["Ingresos", "Ingresos Deuda", "Otros Costos (Op)", "Int. Banco", "Int. KPs", "Int. Relac.", "Pago Capital", "Flujo Neto", "Flujo Acumulado", "Deuda Total"]
        for col in cols_nums:
            df_final[col] = df_final[col].apply(lambda x: f"{x:,.0f} UF".replace(",", ".") if pd.notnull(x) else "0 UF")
        st.dataframe(df_final, use_container_width=True, height=400, column_config={
            "Mes": st.column_config.TextColumn("Mes"),
            "Ingresos": st.column_config.TextColumn("Ingresos"),
            "Ingresos Deuda": st.column_config.TextColumn("Ingresos Deuda"), 
            "Otros Costos (Op)": st.column_config.TextColumn("Otros Costos"),
            "Int. Banco": st.column_config.TextColumn("Int. Banco (Pagado)"),
            "Int. KPs": st.column_config.TextColumn("Int. KPs (Pagado)"),
            "Int. Relac.": st.column_config.TextColumn("Int. Relac. (Pagado)"), # CON PUNTO
            "Pago Capital": st.column_config.TextColumn("Capital"),
            "Flujo Neto": st.column_config.TextColumn("Flujo Neto"),
            "Flujo Acumulado": st.column_config.TextColumn("Acumulado"),
            "Deuda Total": st.column_config.TextColumn("Deuda Viva"),
        })

    # --- ANÁLISIS POR HITOS ---
    st.markdown("---")
    st.markdown("### 📍 Análisis de Intereses Acumulados por Hitos (Devengado Futuro)")
    
    params_real = st.session_state.data_scenarios["Real"]
    mes_inicio_obra = int(params_real.get("mes_inicio_obra", 1))
    duracion_obra = int(params_real.get("duracion_obra", 18))
    mes_construccion = mes_inicio_obra + duracion_obra - 1
    mes_recepcion = int(params_real["mes_recepcion"])
    
    # 1. Recuperamos el Interés Histórico
    int_previos = st.session_state.data_scenarios["Real"].get("intereses_previos_uf", 0.0)
    
    df_real = res["df"]
    try:
        mes_ultimo_recupero = df_real[df_real["Ingresos"] > 0].iloc[-1]["Mes"]
    except IndexError:
        mes_ultimo_recupero = mes_recepcion 
    mes_ultimo_recupero = int(mes_ultimo_recupero)

    milestones = [
        {"nombre": "Término Construcción", "mes": mes_construccion},
        {"nombre": "Recepción Final", "mes": mes_recepcion},
        {"nombre": "Último Recupero (Cierre Deuda)", "mes": mes_ultimo_recupero}
    ]
    
    milestone_data = []
    # 2. El total base para los porcentajes incluye lo histórico
    total_costo_global = res["costo_financiero_total"] + int_previos
    
    for ms in milestones:
        df_cut = df_real[df_real["Mes"] <= ms["mes"]]
        
        # 3. Sumamos el histórico al acumulado del banco
        acum_banco = df_cut["Devengado Banco"].sum() + int_previos
        acum_kps = df_cut["Devengado KPs"].sum()
        acum_relac = df_cut["Devengado Relac."].sum() 
        
        total_acum = acum_banco + acum_kps + acum_relac
        
        pct_avance = (total_acum / total_costo_global * 100) if total_costo_global > 0 else 0
        
        milestone_data.append({
            "Hito": f"{ms['nombre']} (Mes {ms['mes']})",
            "Acum. Banco": fmt_nums(acum_banco),
            "Acum. Privados": fmt_nums(acum_kps + acum_relac),
            "Total Devengado": fmt_nums(total_acum),
            "% del Total": f"{pct_avance:.1f}%"
        })
        
    df_milestones = pd.DataFrame(milestone_data)
    st.dataframe(df_milestones, use_container_width=True, hide_index=True)

    # --- COMPARATIVA ---
    st.markdown("---")
    st.header("⚖️ Comparativa de Escenarios")
    comp_data = []
    for sc in SCENARIOS:
        if sc in st.session_state.calc_results:
            r = st.session_state.calc_results[sc]
            comp_data.append({
                "Escenario": sc,
                "Int. Banco (Dev.)": r["detalles_fin"]["banco"],
                "Int. KPs (Dev.)": r["detalles_fin"]["kps"],
                "Int. Relac. (Dev.)": r["detalles_fin"]["relacionada"],
                "Total Intereses (Dev.)": r["costo_financiero_total"],
                "Mes Break Even": r["break_even"] if r["break_even"] is not None else "N/A"
            })
    df_comp = pd.DataFrame(comp_data)
    c_chart, c_table = st.columns([1.5, 1])
    with c_chart:
        st.subheader("Costos Financieros por Escenario (Devengado)")
        fig_c = go.Figure()
        fig_c.add_trace(go.Bar(name='Banco', x=df_comp['Escenario'], y=df_comp['Int. Banco (Dev.)'], marker_color='#3B82F6', text=df_comp['Int. Banco (Dev.)'].apply(fmt_nums), textposition='auto'))
        fig_c.add_trace(go.Bar(name='KPs', x=df_comp['Escenario'], y=df_comp['Int. KPs (Dev.)'], marker_color='#A855F7', text=df_comp['Int. KPs (Dev.)'].apply(fmt_nums), textposition='auto'))
        fig_c.add_trace(go.Bar(name='Relacionada', x=df_comp['Escenario'], y=df_comp['Int. Relac. (Dev.)'], marker_color='#F97316', text=df_comp['Int. Relac. (Dev.)'].apply(fmt_nums), textposition='auto'))
        fig_c.update_layout(barmode='group', template="plotly_dark", height=350, legend_title="Tipo Interés", font=dict(size=15))
        st.plotly_chart(fig_c, use_container_width=True)
    with c_table:
        st.subheader("Resumen Numérico")
        df_show = df_comp.copy()
        cols_num = ["Int. Banco (Dev.)", "Int. KPs (Dev.)", "Int. Relac. (Dev.)", "Total Intereses (Dev.)"]
        for col in cols_num: df_show[col] = df_show[col].apply(fmt_nums)
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=350)

    # --- GRÁFICOS VISUALES AL FINAL ---
    st.markdown("---")
    st.header("📈 Visualización de Flujo de Caja (Escenario Real)")
    df = res["df"]
    st.markdown("### 🌊 Flujo de Caja")
    fig_cash = go.Figure()
    fig_cash.add_trace(go.Bar(x=df["Mes"], y=df["Flujo Neto"], name="Neto Mensual", marker_color=df["Flujo Neto"].apply(lambda x: '#10B981' if x >= 0 else '#EF4444')))
    fig_cash.add_trace(go.Scatter(x=df["Mes"], y=df["Flujo Acumulado"], name="Acumulado", mode='lines', line=dict(color='#FACC15', width=3, dash='dot')))
    fig_cash.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
    fig_cash.update_layout(template="plotly_dark", height=300, margin=dict(t=30, b=20, l=20, r=20), showlegend=True, font=dict(size=15))
    st.plotly_chart(fig_cash, use_container_width=True)
