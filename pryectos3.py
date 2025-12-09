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
        h1, h2, h3, h4, h5, h6, .stMarkdown, p, label, span { color: #FAFAFA !important; font-family: 'Segoe UI', sans-serif; }
        div[data-baseweb="input"] { background-color: #262730 !important; color: white !important; border: 1px solid #4B5563; }
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
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
        }
        
        div[data-testid="stDataFrame"] { width: 100%; }
        
        /* Botones pequeños para el menú */
        .small-btn { margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- 1. GESTIÓN DE ESTADO ---
SCENARIOS = ["Real", "Optimista", "Pesimista"]

# Inicializar estado de expansión del menú (Por defecto False = Cerrado)
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

        # Deuda Privada
        "prestamo_relacionada": {
            "monto": 5000.0, 
            "tasa_anual": 8.0,
            "frecuencia_pago": "Al Final"
        },
        "lista_kps": [
            {"nombre": "KP 1", "monto": 2000.0, "tasa_anual": 12.0, "plazo": 24, "frecuencia_pago": "Mensual"}
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
    rel_data = data.get("prestamo_relacionada", {"monto": 0, "tasa_anual": 0})
    saldo_relacionada = rel_data["monto"]
    tasa_mensual_rel = (rel_data["tasa_anual"] / 100) / 12
    frecuencia_rel = rel_data.get("frecuencia_pago", "Al Final")
    acumulado_trimestre_rel = 0
    
    kps_activos = []
    for kp in data.get("lista_kps", []):
        kps_activos.append({
            "saldo": kp["monto"],
            "tasa_mensual": (kp["tasa_anual"] / 100) / 12,
            "plazo": kp["plazo"],
            "frecuencia": kp.get("frecuencia_pago", "Mensual"), 
            "acumulado_trimestre": 0, 
            "interes_acumulado_hist": 0
        })

    # Recuperos
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
    
    flujo.append({
        "Mes": 0,
        "Deuda Total": (saldo_const_uf + saldo_terr_uf) + (saldo_const_clp_nominal + saldo_terr_clp_nominal) + saldo_relacionada + sum(k['saldo'] for k in kps_activos),
        "Ingresos": 0.0,
        "Otros Costos (Op)": 0.0,
        "Pago Intereses": 0.0,
        "Pago Capital": 0.0,
        "Inversión (Equity)": inversion_inicial,
        "Flujo Neto": -inversion_inicial,
        "Flujo Acumulado": -inversion_inicial
    })
    
    # Acumuladores KPI
    interes_acum_banco_total = 0 
    interes_acum_kps = 0
    interes_acum_relacionada = 0
    total_otros_costos_operativos = 0 
    
    factor_uf = 1.0 
    acumulado_actual = -inversion_inicial
    mes_break_even = None
    
    for m in range(1, horizonte + 1):
        factor_uf *= (1 + inflacion_mensual)
        
        # 1. GENERACIÓN DE DEUDA BANCARIA (GIROS)
        egreso_equity_const = 0
        if m <= duracion:
            costo_mes_total = v_cont / duracion
            giro_banco = costo_mes_total * pct_fin_const
            egreso_equity_const = costo_mes_total - giro_banco 
            
            saldo_const_uf += giro_banco * pct_uf
            saldo_const_clp_nominal += (giro_banco * pct_clp) * factor_uf 

        # 2. CÁLCULO DE INTERESES DEL MES (DEVENGADOS)
        
        # A. Banco
        int_uf_mes = (saldo_const_uf + saldo_terr_uf) * tasa_mensual_uf
        if m == 1: saldo_terr_clp_nominal *= 1.0 
        int_clp_nom_mes = (saldo_const_clp_nominal + saldo_terr_clp_nominal) * tasa_mensual_clp
        int_banco_mes_en_uf = int_uf_mes + (int_clp_nom_mes / factor_uf)
        
        saldo_const_uf += int_uf_mes
        saldo_const_clp_nominal += int_clp_nom_mes
        interes_acum_banco_total += int_banco_mes_en_uf

        # B. KPs (Con Lógica de Frecuencia)
        int_kps_generado_mes = 0 
        total_interes_kp_exigible_hoy = 0 
        
        for kp in kps_activos:
            if kp["saldo"] > 0:
                ik = kp["saldo"] * kp["tasa_mensual"]
                kp["interes_acumulado_hist"] += ik
                int_kps_generado_mes += ik
                
                # Gestión Frecuencia KP
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
        
        # C. Relacionada (Con Lógica de Frecuencia)
        int_rel_mes = 0
        interes_rel_exigible_hoy = 0
        
        if saldo_relacionada > 0:
            int_rel_mes = saldo_relacionada * tasa_mensual_rel
            
            if frecuencia_rel == "Mensual":
                saldo_relacionada += int_rel_mes
                interes_rel_exigible_hoy = int_rel_mes
            elif frecuencia_rel == "Trimestral":
                saldo_relacionada += int_rel_mes
                acumulado_trimestre_rel += int_rel_mes
                if m % 3 == 0:
                    interes_rel_exigible_hoy = acumulado_trimestre_rel
                    acumulado_trimestre_rel = 0
            else: # Al Final
                saldo_relacionada += int_rel_mes
                interes_rel_exigible_hoy = 0
        
        interes_acum_relacionada += int_rel_mes
        
        # 3. FLUJO OPERATIVO
        ingreso_uf = sum([r["Monto"] for r in recuperos if r["Mes"] == m])
        gasto_operativo_mes = v_otros_mensual if (m <= recepcion + 6) else 0 
        total_otros_costos_operativos += gasto_operativo_mes
        
        flujo_operativo = ingreso_uf - gasto_operativo_mes
        dinero_para_deuda = max(0.0, flujo_operativo)
        
        # 4. WATERFALL DE PAGOS
        
        # --- A. BANCO ---
        real_const_uf = saldo_const_uf + (saldo_const_clp_nominal / factor_uf)
        real_terr_uf = saldo_terr_uf + (saldo_terr_clp_nominal / factor_uf)
        deuda_banco_total = real_const_uf + real_terr_uf
        
        pago_banco_total = 0
        pago_banco_interes = 0
        pago_banco_capital = 0

        if dinero_para_deuda > 0 and deuda_banco_total > 0:
            monto_a_pagar_banco = min(deuda_banco_total, dinero_para_deuda)
            pago_banco_interes = min(monto_a_pagar_banco, int_banco_mes_en_uf)
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
            
            if p_terr > 0 and real_terr_uf > 0:
                prop = p_terr / real_terr_uf
                saldo_terr_uf -= (saldo_terr_uf * prop)
                saldo_terr_clp_nominal -= (saldo_terr_clp_nominal * prop)

            if p_const > 0 and real_const_uf > 0:
                prop = p_const / real_const_uf
                saldo_const_uf -= (saldo_const_uf * prop)
                saldo_const_clp_nominal -= (saldo_const_clp_nominal * prop)
            
            pago_banco_total = monto_a_pagar_banco
            dinero_para_deuda -= pago_banco_total

        # --- B. KPs ---
        pago_kps_total = 0
        pago_kps_interes = 0
        saldo_total_kps_contable = sum(k['saldo'] for k in kps_activos)
        
        if dinero_para_deuda > 0 and saldo_total_kps_contable > 0:
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
        
        if dinero_para_deuda > 0 and saldo_relacionada > 0:
            # 1. Pago Intereses Exigibles
            monto_interes_rel_pagar = min(dinero_para_deuda, interes_rel_exigible_hoy)
            saldo_relacionada -= monto_interes_rel_pagar
            pago_rel_interes = monto_interes_rel_pagar
            dinero_para_deuda -= pago_rel_interes
            
            # 2. Pago Capital Relacionada
            if dinero_para_deuda > 0:
                monto_capital_rel = min(dinero_para_deuda, saldo_relacionada)
                saldo_relacionada -= monto_capital_rel
                pago_rel_total = pago_rel_interes + monto_capital_rel
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
        
        if acumulado_actual >= 0 and mes_break_even is None:
            mes_break_even = m

        deuda_banco_reporte = (saldo_const_uf + saldo_terr_uf) + ((saldo_const_clp_nominal + saldo_terr_clp_nominal) / factor_uf)

        flujo.append({
            "Mes": m,
            "Deuda Banco": deuda_banco_reporte,
            "Deuda KPs": saldo_kps_reporte,
            "Deuda Relac.": saldo_relacionada,
            "Deuda Total": deuda_banco_reporte + saldo_kps_reporte + saldo_relacionada,
            "Ingresos": ingreso_uf,
            "Otros Costos (Op)": gasto_operativo_mes,
            "Inversión (Equity)": egreso_equity_const,
            "Pago Intereses": total_pagado_intereses,
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

with col_inputs:
    st.markdown("### Configuración")
    
    # --- LOGICA BOTONES EXPANDIR/CERRAR TODO ---
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("🔽 Expandir Todo", key="btn_expand", use_container_width=True):
        st.session_state.menu_expanded = True
        st.rerun()
    if col_btn2.button("🔼 Colapsar Todo", key="btn_collapse", use_container_width=True):
        st.session_state.menu_expanded = False
        st.rerun()
    # ---------------------------------------------
    
    tabs = st.tabs(["🟦 Real", "🟩 Optimista", "🟥 Pesimista"])
    
    def render_scenario_inputs(scen_key):
        data = st.session_state.data_scenarios[scen_key]
        
        # Obtenemos el estado actual de expansión
        is_expanded = st.session_state.menu_expanded
        
        with st.container():
            with st.expander("🏗️ Proyecto Base & Costos", expanded=is_expanded):
                data["valor_terreno"] = st.number_input("Valor Terreno (UF)", value=data["valor_terreno"], key=f"{scen_key}_vt")
                data["pct_fin_terreno"] = st.slider("% Fin. Terreno", 0, 100, data["pct_fin_terreno"], key=f"{scen_key}_fin_t")
                data["valor_contrato"] = st.number_input("Costo Const. (UF)", value=data["valor_contrato"], key=f"{scen_key}_vc")
                data["pct_fin_construccion"] = st.slider("% Fin. Construcción", 0, 100, data["pct_fin_construccion"], key=f"{scen_key}_fin_c")
                data["duracion_obra"] = st.number_input("Meses Obra", value=data["duracion_obra"], key=f"{scen_key}_dur")
                data["saldo_inicial_uf"] = st.number_input("Saldo Inicial Banco (UF)", value=data.get("saldo_inicial_uf", 0.0), key=f"{scen_key}_ini")
                
                st.markdown("---")
                st.caption("📋 Otros Costos No Financieros")
                data["total_otros_costos_inicial"] = st.number_input("Otros Costos Iniciales (Permisos, Arq)", value=data.get("total_otros_costos_inicial", 0.0), key=f"{scen_key}_oci")
                data["otros_costos_mensuales"] = st.number_input("Gasto Operativo Mensual (Admin, Ventas)", value=data.get("otros_costos_mensuales", 0.0), key=f"{scen_key}_ocm")

            with st.expander("🏦 Deuda Bancaria", expanded=is_expanded):
                data["pct_deuda_pesos"] = st.slider("% Deuda CLP", 0, 100, data["pct_deuda_pesos"], key=f"{scen_key}_mix")
                
                c1, c2, c3 = st.columns(3)
                data["tasa_anual_uf"] = c1.number_input("Tasa UF", value=data["tasa_anual_uf"], step=0.1, key=f"{scen_key}_tuf")
                data["tasa_anual_clp"] = c2.number_input("Tasa CLP", value=data["tasa_anual_clp"], step=0.1, key=f"{scen_key}_tclp")
                data["inflacion_anual"] = c3.number_input("Infl. %", value=data["inflacion_anual"], step=0.1, key=f"{scen_key}_inf")
                
                st.markdown("**Pago Terreno**")
                rango_val = data.get("rango_pago_terreno", [1, 60])
                data["rango_pago_terreno"] = st.slider("Ventana Pago", 1, 60, (rango_val[0], rango_val[1]), key=f"{scen_key}_rng")
                data["prioridad_terreno"] = st.checkbox("Prioridad Terreno", value=data.get("prioridad_terreno", False), key=f"{scen_key}_prio")

            with st.expander("🤝 Deuda Privada (KPs y Relac.)", expanded=is_expanded):
                st.markdown("##### Préstamo Relacionada")
                cr1, cr2 = st.columns(2)
                data["prestamo_relacionada"]["monto"] = cr1.number_input("Monto (UF)", value=data["prestamo_relacionada"]["monto"], key=f"{scen_key}_rel_mnt")
                data["prestamo_relacionada"]["tasa_anual"] = cr2.number_input("Tasa Anual (%)", value=data["prestamo_relacionada"]["tasa_anual"], step=0.1, key=f"{scen_key}_rel_tas")
                data["prestamo_relacionada"]["frecuencia_pago"] = st.selectbox("Pago Interés Relac.", ["Mensual", "Trimestral", "Al Final"], index=["Mensual", "Trimestral", "Al Final"].index(data["prestamo_relacionada"].get("frecuencia_pago", "Al Final")), key=f"{scen_key}_rel_freq")

                st.markdown("---")
                st.markdown("##### Inversionistas (KPs)")
                
                if st.button("➕ Agregar KP", key=f"add_kp_{scen_key}"):
                    data["lista_kps"].append({"nombre": f"KP {len(data['lista_kps'])+1}", "monto": 1000.0, "tasa_anual": 10.0, "plazo": 24, "frecuencia_pago": "Mensual"})
                    st.rerun()

                idx_kp_remove = []
                for i, kp in enumerate(data["lista_kps"]):
                    st.markdown(f"**KP #{i+1}**")
                    k1, k2 = st.columns(2)
                    kp["monto"] = k1.number_input("Monto", value=float(kp["monto"]), key=f"kpm_{scen_key}_{i}")
                    kp["tasa_anual"] = k2.number_input("Tasa %", value=float(kp["tasa_anual"]), step=0.1, key=f"kpt_{scen_key}_{i}")
                    
                    k3, k4 = st.columns([2, 1])
                    kp["plazo"] = k3.number_input("Plazo", value=int(kp["plazo"]), key=f"kpp_{scen_key}_{i}")
                    kp["frecuencia_pago"] = k3.selectbox("Pago Interés", ["Mensual", "Trimestral", "Al Final"], index=["Mensual", "Trimestral", "Al Final"].index(kp.get("frecuencia_pago", "Mensual")), key=f"kpf_{scen_key}_{i}")
                    
                    if k4.button("🗑️", key=f"del_kp_{scen_key}_{i}"):
                        idx_kp_remove.append(i)
                    st.divider()
                
                if idx_kp_remove:
                    for i in sorted(idx_kp_remove, reverse=True):
                        data["lista_kps"].pop(i)
                    st.rerun()

            with st.expander("💰 Plan de Ventas", expanded=is_expanded):
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

# --- DASHBOARD ---
results = {name: calcular_flujo(st.session_state.data_scenarios[name]) for name in SCENARIOS}

with col_dash:
    res = results["Real"]
    
    st.markdown("### 🏆 KPIs Escenario Real")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Utilidad", f"{res['utilidad']:,.0f} UF")
    k2.metric("ROI Proyecto", f"{res['roi']:.1f}%")
    k3.metric("Mes flujo positivo", f"Mes {res['break_even']}" if res['break_even'] else "N/A")
    k4.metric("Peak Deuda", f"{res['peak_deuda']:,.0f} UF")

    # --- NUEVA TARJETA DE INTERESES ---
    st.markdown("#### 💳 Costos Financieros (Acumulado)")
    with st.container():
        st.markdown('<div class="interest-card">', unsafe_allow_html=True)
        st.markdown('<div class="interest-title">Desglose de Intereses Proyectados</div>', unsafe_allow_html=True)
        
        det = res["detalles_fin"]
        ic1, ic2, ic3, ic4 = st.columns(4)
        
        ic1.metric("🏦 Banco", f"{det['banco']:,.0f} UF")
        ic2.metric("🤝 Total KPs", f"{det['kps']:,.0f} UF")
        ic3.metric("🏢 Relacionada", f"{det['relacionada']:,.0f} UF")
        ic4.metric("💰 TOTAL GLOBAL", f"{res['costo_financiero_total']:,.0f} UF", delta="Interés Total")
        
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### 🧱 Composición Deuda Total")
    df = res["df"]
    
    fig_stack = go.Figure()
    fig_stack.add_trace(go.Scatter(
        x=df["Mes"], y=df["Deuda Banco"], mode='lines', stackgroup='one', name='Banco', line=dict(color='#3B82F6')
    ))
    fig_stack.add_trace(go.Scatter(
        x=df["Mes"], y=df["Deuda KPs"], mode='lines', stackgroup='one', name='KPs', line=dict(color='#A855F7')
    ))
    fig_stack.add_trace(go.Scatter(
        x=df["Mes"], y=df["Deuda Relac."], mode='lines', stackgroup='one', name='Relacionada', line=dict(color='#F97316')
    ))
    fig_stack.update_layout(template="plotly_dark", height=300, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig_stack, use_container_width=True)

    st.markdown("### 🌊 Flujo de Caja")
    fig_cash = go.Figure()
    fig_cash.add_trace(go.Bar(
        x=df["Mes"], y=df["Flujo Neto"], name="Neto Mensual",
        marker_color=df["Flujo Neto"].apply(lambda x: '#10B981' if x >= 0 else '#EF4444')
    ))
    fig_cash.add_trace(go.Scatter(
        x=df["Mes"], y=df["Flujo Acumulado"], name="Acumulado", mode='lines',
        line=dict(color='#FACC15', width=3, dash='dot')
    ))
    fig_cash.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
    fig_cash.update_layout(template="plotly_dark", height=300, margin=dict(t=30, b=20, l=20, r=20), showlegend=True)
    st.plotly_chart(fig_cash, use_container_width=True)

    with st.expander("📋 Tabla Detallada (Verificación de Pagos)", expanded=False):
        cols_show = ["Mes", "Ingresos", "Otros Costos (Op)", "Pago Intereses", "Pago Capital", "Flujo Neto", "Flujo Acumulado", "Deuda Total"]
        st.dataframe(df[cols_show], use_container_width=True, height=400)
