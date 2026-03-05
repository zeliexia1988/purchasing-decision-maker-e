
import streamlit as st
import pandas as pd
import os
st.write("程序当前运行目录：", os.getcwd())
st.write("该目录下的文件：", os.listdir("."))

from datetime import datetime
import urllib.parse

# 设置网页标题
st.set_page_config(page_title="SADE 采购决策支持系统", layout="wide")

# ===============================
# 1. 读取数据
# ===============================
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("contracts_b.xlsx")
        # 确保数据类型正确，避免计算报错
        df["DE"] = pd.to_numeric(df["DE"], errors='coerce')
        df["PN"] = pd.to_numeric(df["PN"], errors='coerce')
        df["Price"] = pd.to_numeric(df["Price"], errors='coerce')
        return df
    except Exception as e:
        st.error(f"无法读取文件: {e}")
        return None

contracts = load_data()

# ===============================
# 2. 核心计算与显示函数
# ===============================
def calculate_all_totals(material, de, pn, quantity, package, today):
    """
    找到所有符合条件的合同，并计算各自的总价。
    """
    pkg_str = str(package).lower() if package else ""
    # 筛选匹配的合同
    mask = (
        (contracts["Material"] == material) &
        (contracts["Valid_Until"] >= today) &
        (contracts["DE"] == float(de)) &
        (contracts["PN"] == float(pn)) &
        (contracts["Package"].astype(str).str.lower() == pkg_str)
    )
    valid_matches = contracts[mask].copy()

    if valid_matches.empty:
        return None

    # 计算总价
    valid_matches["Total_HT"] = valid_matches["Price"] * quantity
    
    # 排序：价格从低到高
    valid_matches = valid_matches.sort_values("Price")

    # 格式化表格用于显示
    display_df = valid_matches[["Supplier", "Price", "Total_HT"]].copy()
    display_df.columns = ["Fournisseur", "Prix Unitaire (€/ml)", "Montant Total (HT)"]
    
    # 格式化数字显示
    display_df["Prix Unitaire (€/ml)"] = display_df["Prix Unitaire (€/ml)"].map("{:.2f} €".format)
    display_df["Montant Total (HT)"] = display_df["Montant Total (HT)"].map("{:,.2f} €".format)
    
    return display_df

# ===============================
# 3. 采购规则函数 (保持原样)
# ===============================
def rule_distributor_purchase(quantity, package, DE):
    return (package == "couronne" or DE < 125 or (DE < 200 and quantity < 1200))

def rule_contract_purchase(quantity, package, DE):
    return ((package == "barre" and 125 <= DE <= 200 and 1200 <= quantity)
            or (package == "barre" and 225 <= DE <= 315 and quantity < 2000))

def rule_factory_purchase(quantity, package, DE):
    return ((package == "barre" and 225 <= DE <= 315 and 2000 <= quantity) or package.lower() == "touret" or (package == "barre" and 315 < DE))

def rule_distributor_purchase_dipipe(quantity, DE):
    return (DE < 80)

def rule_contract_purchase_dipipe(quantity, DE):
    return ((DE >= 80 and quantity <= 968) or (DE >= 100 and quantity <= 891) or 
            (DE >= 125 and quantity <= 770) or (DE >= 150 and quantity <= 594) or 
            (DE >= 200 and quantity <= 440) or (DE >= 250 and quantity <= 396) or 
            (DE >= 300 and quantity <= 264))

def rule_factory_purchase_dipipe(quantity, DE):
    return not rule_contract_purchase_dipipe(quantity, DE) and DE >= 80

def generate_email_template(supplier, material, quantity, de, pn, package):
    subject = f"Demande de prix - {material} - DE{de} PN{pn}"
    body = f"Bonjour,\n\nDans le cadre d'un nouveau projet, nous souhaiterions obtenir votre meilleure offre pour :\n- Produit : {material}\n- DE : {de} / PN : {pn}\n- Quantité : {quantity} ml\n- Conditionnement : {package}\n\nCordialement,"
    return subject, body

# ===============================
# 4. Streamlit 界面
# ===============================
st.title("🛡️ SADE Purchasing Decision")

if contracts is not None:
    with st.form("purchase_form"):
        col1, col2 = st.columns(2)
        mat_options = [""] + sorted(contracts["Material"].dropna().unique().tolist())
        pkg_options = ["", "couronne", "barre", "touret"]
        de_options = [""] + sorted([int(x) for x in contracts["DE"].dropna().unique()])
        pn_options = [""] + sorted([float(x) for x in contracts["PN"].dropna().unique()])
        
        with col1:
            material_choice = st.selectbox("Matériau:", options=mat_options)
            package_choice = st.selectbox("Conditionnement:", options=pkg_options)
            qty_input = st.number_input("Quantité (ml):", min_value=0, step=1)
        
        with col2:
            de_choice = st.selectbox("DE (Diamètre):", options=de_options)
            pn_choice = st.selectbox("PN (Pression):", options=pn_options)
        
        submit_btn = st.form_submit_button("Run Decision", type="primary")
        
    if submit_btn:
        if not material_choice or not package_choice or not de_choice or not pn_choice:
            st.warning("⚠️ Veuillez remplir tous les champs.")
        else:
            today = datetime.today()
            st.divider()
            
            # --- 逻辑判断与结果展示 ---
            decision_msg = ""
            show_prices = False
            target_supplier = "Fournisseur"

            if "fonte" in material_choice.lower():
                if rule_factory_purchase_dipipe(qty_input, de_choice):
                    decision_msg = "✅ Decision: Consultation Electrosteel sous contrat"
                    show_prices = True
                elif rule_contract_purchase_dipipe(qty_input, de_choice):
                    decision_msg = "✅ Decision: Application tarif contractuel Electrosteel"
                    show_prices = True
                else:
                    decision_msg = "🛒 Decision: Consultation Négoce"
            else:
                if package_choice.lower() == "touret":
                    decision_msg = "✅ Décision: Consultation Elydan (Délai 4-6 sem)"
                    show_prices = True
                elif rule_factory_purchase(qty_input, package_choice, de_choice):
                    decision_msg = "✅ Decision: Consultation Fabricant (Elydan, Centraltubi)"
                    show_prices = True
                elif rule_contract_purchase(qty_input, package_choice, de_choice):
                    decision_msg = "✅ Decision: Application tarif contractuelle"
                    show_prices = True
                else:
                    decision_msg = "🛒 Decision: Consultation Négoce"

            st.subheader(decision_msg)

            # --- 显示计算出的总价表格 ---
            if show_prices:
                price_table = calculate_all_totals(material_choice, de_choice, pn_choice, qty_input, package_choice, today)
                if price_table is not None:
                    st.write("### 💰 Comparatif des prix contractuels")
                    st.table(price_table)
                else:
                    st.info("ℹ️ Aucun prix contractuel valide trouvé dans la base pour ces critères.")

            # --- 邮件草稿 ---
            if "Consultation" in decision_msg:
                st.info("📧 **Brouillon d'Email**")
                subject, body = generate_email_template(target_supplier, material_choice, qty_input, de_choice, pn_choice, package_choice)

                st.text_area("Copier :", value=body, height=150)






