from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pdfplumber
import io
import re
from datetime import datetime

router = APIRouter()

# Configuração do Jinja2 para templates HTML
env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

def parse_mind7_pdf_to_data(file_bytes: bytes) -> dict:
    """
    Parser do relatório MIND-7 (CPF) para o modelo de dados do relatório Delta Trace.
    - Usa pdfplumber para extrair texto
    - Trabalha linha a linha
    - Usa regex para capturar datas, CEP, telefones, etc.
    """
    # ---- 1. Extrair texto bruto ----
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        texts = [page.extract_text() or "" for page in pdf.pages]

    full_text = "\n".join(texts)
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]

    # Helpers
    def find_line(label: str, start: int = 0) -> int:
        for i in range(start, len(lines)):
            if lines[i] == label or lines[i].endswith(label):
                return i
        return -1

    def val_after(label: str, start: int = 0, default: str = "Não informado"):
        idx = find_line(label, start)
        if idx != -1 and idx + 1 < len(lines):
            return lines[idx + 1].strip(), idx + 1
        return default, -1

    # ---- 2. META / CABEÇALHO ----
    meta_match = re.match(r"(\d{2}/\d{2}/\d{4}, \d{2}:\d{2})", lines[0])
    meta_data = meta_match.group(1) if meta_match else ""

    # ---- 3. DADOS BÁSICOS ----
    nome, _ = val_after("Nome Completo")
    mae, _ = val_after("Nome da Mãe")
    pai, _ = val_after("Nome do Pai")
    cpf_raw, _ = val_after("CPF")
    data_nasc, _ = val_after("Data de Nascimento")
    sexo_raw, _ = val_after("Sexo")
    estado_civil, _ = val_after("Estado Civil")
    renda_val, _ = val_after("Renda")
    faixa_renda, _ = val_after("Faixa de Renda")
    nacionalidade, _ = val_after("Nacionalidade")
    email_cadastral, _ = val_after("Email")
    dt_atualizacao, _ = val_after("Data Atualização")
    codigo_controle, _ = val_after("Código Controle")

    def format_cpf(cpf: str) -> str:
        digits = re.sub(r"\D", "", cpf or "")
        if len(digits) == 11:
            return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"
        return cpf

    cpf_fmt = (
        f"{format_cpf(cpf_raw)} (Regular)"
        if cpf_raw not in ("", "Não informado")
        else "Não informado"
    )
    sexo = {"F": "Feminino", "M": "Masculino"}.get(
        (sexo_raw or "").strip().upper(), sexo_raw
    )

    identificacao = {
        "nome": nome,
        "cpf_formatado": cpf_fmt,
        "data_nasc": data_nasc,
        "sexo": sexo,
        "estado_civil": estado_civil,
        "mae": mae,
        "pai": pai,
        "nacionalidade": (
            "Brasileiro(a)"
            if not nacionalidade or nacionalidade == "Não informado"
            else nacionalidade
        ),
        "profissao": "Não informado",
        "renda_declarada": (
            f"{renda_val} (Faixa {faixa_renda})"
            if renda_val != "Não informado"
            else "Não informado"
        ),
        "email_cadastral": email_cadastral,
        "data_atualizacao": dt_atualizacao,
        "codigo_controle": codigo_controle,
    }

    # ---- 4. RECEITA FEDERAL ----
    rf_start = find_line("RECEITA FEDERAL (2023)")

    def val_after_rf(label: str, default: str = "Não informado") -> str:
        if rf_start == -1:
            return default
        v, _ = val_after(label, start=rf_start)
        return v

    rf = {
        "nome": val_after_rf("Nome"),
        "cpf": val_after_rf("CPF"),
        "titulo": val_after_rf("Titulo Eleitor"),
        "sexo": val_after_rf("Sexo"),
        "nascimento": val_after_rf("Nascimento"),
        "situacao": val_after_rf("Situação Cadastral"),
        "nacionalidade": val_after_rf("Nacionalidade"),
        "residente_exterior": val_after_rf("Residente Exterior"),
        "endereco": val_after_rf("Endereço"),
        "telefone": val_after_rf("Telefone"),
        "atualizacao": val_after_rf("Data Atualização"),
        "log_nome": "",
    }

    idx_nome_rec = find_line("NOME NA RECEITA")
    if idx_nome_rec != -1 and idx_nome_rec + 2 < len(lines):
        partes = lines[idx_nome_rec + 2].split()
        if len(partes) >= 3:
            rf["log_nome"] = " ".join(partes[-2:])

    # ---- 5. ESCOLARIDADE / PROFISSÕES / RAIS ----
    esc_idx = find_line("NÍVEL DATA INCLUSÃO")
    escolaridade = "Não informado"
    profissoes = []
    rais = "Não informado"

    if esc_idx != -1:
        if esc_idx + 1 < len(lines):
            escolaridade = lines[esc_idx + 1]

        prof_idx = find_line("HISTÓRICO PROFISSIONAL", start=esc_idx)
        rais_idx = find_line("RAIS", start=esc_idx)

        if prof_idx != -1:
            i = prof_idx + 2  # pula cabeçalho
            while i < len(lines) and (rais_idx == -1 or i < rais_idx):
                if i + 1 < len(lines) and re.search(r"\d{2}/\d{2}/\d{4}", lines[i + 1]):
                    profissoes.append({"cargo": lines[i], "data": lines[i + 1]})
                    i += 2
                else:
                    i += 1

        if rais_idx != -1 and rais_idx + 2 < len(lines):
            rais = lines[rais_idx + 2]

    # ---- 6. TELEFONES ----
    tels = []
    tel_header = find_line("TELEFONES")
    histop_idx = find_line("HISTÓRICO OPERADORAS")

    if tel_header != -1:
        i = tel_header + 1
        while i < len(lines) and (histop_idx == -1 or i < histop_idx):
            line = lines[i]
            if re.search(r"\(\d{2}\)\s*[\d-]+", line):
                m = re.search(r"\(\d{2}\)\s*[\d-]+", line)
                numero = m.group(0)
                m2 = re.search(r"\d{2}/\d{2}/\d{4}", line)
                data_incl = m2.group(0) if m2 else ""
                l2 = lines[i + 1] if i + 1 < len(lines) else ""
                m3 = re.search(r"\d{2}/\d{2}/\d{4}|N/I", l2)
                atual = m3.group(0) if m3 else ""
                m4 = re.search(r"PRIORIDADE:\s*([0-9.]+)", l2)
                prio = m4.group(1) if m4 else ""
                tels.append(
                    {
                        "numero": numero,
                        "atualizacao": atual or data_incl,
                        "prioridade": prio,
                        "obs": "WhatsApp ativo" if "" in l2 else "",
                    }
                )
                i += 2
            else:
                i += 1

    # ---- 7. HISTÓRICO DE OPERADORAS ----
    operadoras = []
    histop_idx = find_line("TELEFONE DATA OPERADORA ATALHO")
    email_idx = find_line("✉  E-MAILS")
    
    # Fallback se não achar o símbolo exato
    if email_idx == -1:
        email_idx = find_line("E-MAILS")

    if histop_idx != -1:
        i = histop_idx + 1
        while i < len(lines) and (email_idx == -1 or i < email_idx):
            if re.search(r"\(\d{2}\)\s*[\d-]+", lines[i]):
                tel = lines[i]
                dataop = lines[i + 1] if i + 1 < len(lines) else ""
                oper = lines[i + 2] if i + 2 < len(lines) else ""
                operadoras.append({"telefone": tel, "data": dataop, "operadora": oper})
                i += 3
            else:
                i += 1

    # ---- 8. E-MAILS ----
    emails = []
    possible_email_headers = ["✉  E-MAILS", "E-MAILS", "E-MAIL", "EMAILS", "EMAIL"]
    
    actual_email_idx = -1
    for header in possible_email_headers:
        actual_email_idx = find_line(header)
        if actual_email_idx != -1:
            break

    ender_idx = find_line("ENDEREÇOS", start=actual_email_idx) if actual_email_idx != -1 else -1

    if actual_email_idx != -1:
        i = actual_email_idx + 1
        while i < len(lines) and (ender_idx == -1 or i < ender_idx):
            line = lines[i]
            if "@" in line:
                email = line.strip()
                date = ""
                # Procura data nos próximos 5 itens
                for j in range(i + 1, min(i + 6, len(lines))):
                    m = re.search(r"\d{2}/\d{2}/\d{4}", lines[j])
                    if m:
                        date = m.group(0)
                        break
                emails.append({"email": email, "data": date})
            i += 1

    # ---- 9. ENDEREÇOS ----
    enderecos = []
    ender_idx = find_line("ENDEREÇOS")
    parentes_idx = find_line("PARENTES", start=ender_idx) if ender_idx != -1 else -1

    if ender_idx != -1:
        addr_lines = (
            lines[ender_idx + 2 : parentes_idx]
            if parentes_idx != -1
            else lines[ender_idx + 2 :]
        )

        for i, line in enumerate(addr_lines):
            if line.startswith("Prioridade:"):
                prio = line.split(":", 1)[1].strip()

                # Volta até achar o "Bairro:"
                bairro_idx = None
                for j in range(i - 1, -1, -1):
                    if addr_lines[j].startswith("Bairro:"):
                        bairro_idx = j
                        break
                if bairro_idx is None:
                    continue

                bairro_line = addr_lines[bairro_idx]
                cidade_line = addr_lines[bairro_idx - 1] if bairro_idx - 1 >= 0 else ""
                addr_line = addr_lines[bairro_idx - 2] if bairro_idx - 2 >= 0 else ""
                tipo = addr_line.split()[0] if addr_line else ""

                # CEP Extractor
                cep = ""
                m1 = re.search(r"(\d{5})-", cidade_line)
                m2 = re.search(r"(\d{3})\s+\d{2}:\d{2}:\d{2}", bairro_line)
                if m1 and m2:
                    cep = f"{m1.group(1)}-{m2.group(1)}"
                else:
                    mcep = re.search(r"(\d{5}-\d{3})", cidade_line + " " + bairro_line)
                    if mcep:
                        cep = mcep.group(1)
                    else:
                        mcep2 = re.search(r"(\d{5}-)\s*(\d{3})", cidade_line + " " + bairro_line)
                        if mcep2:
                            cep = mcep2.group(1) + mcep2.group(2)

                mdt = re.search(r"\d{2}/\d{2}/\d{4}", cidade_line + " " + bairro_line)
                data_atual = mdt.group(0) if mdt else "Não informado"

                mcity = re.search(r"[A-ZÇÃÉÍÓÚ]+/[A-Z]{2}", cidade_line)
                cidade_uf = mcity.group(0) if mcity else cidade_line

                enderecos.append(
                    {
                        "tipo": tipo,
                        "endereco": addr_line,
                        "cidade_uf": cidade_uf,
                        "cep": cep,
                        "atualizacao": data_atual,
                        "prioridade": prio,
                    }
                )

    # ---- 10. PARENTES ----
    parentes = []
    par_idx = find_line("PARENTES")
    mosaic_anchor = find_line("CLASSE SOCIAL", start=par_idx) if par_idx != -1 else -1

    def linha_invalida(txt: str) -> bool:
        return (
            "http" in txt.lower()
            or "mind7" in txt.lower()
            or "consultas" in txt.lower()
            or "vinculo" in txt.lower()
            or ("/" in txt and " " in txt and txt.count("/") > 3)
        )

    if par_idx != -1:
        i = par_idx + 2
        while i < len(lines) and (mosaic_anchor == -1 or i < mosaic_anchor):
            if linha_invalida(lines[i]):
                i += 1
                continue

            vinc = lines[i].strip()
            if (
                i + 2 < len(lines)
                and not linha_invalida(lines[i + 1])
                and not linha_invalida(lines[i + 2])
            ):
                parentes.append(
                    {
                        "vinculo": vinc,
                        "nome": lines[i + 1].strip(),
                        "cpf": lines[i + 2].strip(),
                    }
                )
                i += 3
            else:
                i += 1

    # ---- 11. PERFIL SOCIOECONÔMICO ----
    perfil_socio = {
        "classe_social": "",
        "renda_modelada": "",
        "poder_aquisitivo": "",
        "target_renda": "",
        "risco_credito": "",
    }

    classe_idx = find_line("CLASSE SOCIAL")
    if classe_idx != -1:
        if classe_idx + 2 < len(lines):
            perfil_socio["classe_social"] = lines[classe_idx + 2]

        renda_idx = find_line("INFORMAÇÕES DE CRÉDITO", start=classe_idx)
        if renda_idx != -1 and renda_idx + 2 < len(lines):
            perfil_socio["renda_modelada"] = (
                lines[renda_idx + 2] + " " + (lines[renda_idx + 3] if renda_idx + 3 < len(lines) else "")
            )

        poder_idx = find_line("PODER AQUISITIVO", start=classe_idx)
        if poder_idx != -1 and poder_idx + 2 < len(lines):
            perfil_socio["poder_aquisitivo"] = " ".join(lines[poder_idx + 2 : poder_idx + 5])

        target_idx = find_line("TARGET DE RENDA", start=classe_idx)
        if target_idx != -1 and target_idx + 2 < len(lines):
            perfil_socio["target_renda"] = " ".join(lines[target_idx + 2 : target_idx + 5])

        risco_idx = find_line("RISCO DE CRÉDITO", start=classe_idx)
        if risco_idx != -1 and risco_idx + 2 < len(lines):
            perfil_socio["risco_credito"] = " ".join(lines[risco_idx + 2 : risco_idx + 6])

    # ---- 12. MOSAIC ----
    mosaic = {"segmento_credito": "", "segmento_target": ""}
    seg1_idx = find_line("Segmento")
    if seg1_idx != -1:
        mosaic["segmento_credito"] = " ".join(lines[seg1_idx + 1 : seg1_idx + 6])
        seg2_idx = find_line("Segmento", start=seg1_idx + 1)
        if seg2_idx != -1:
            mosaic["segmento_target"] = " ".join(lines[seg2_idx + 1 : seg2_idx + 6])

    # ---- 13. DOCUMENTOS ----
    docs = {"pis": "", "nis": "", "rg": "", "irpf": ""}
    docs_idx = find_line("DOCUMENTOS")
    if docs_idx != -1:
        docs["pis"], _ = val_after("PIS", start=docs_idx)
        docs["nis"], _ = val_after("NIS", start=docs_idx)
        docs["rg"], _ = val_after("RG", start=docs_idx)
        irpf_idx = find_line("IMPOSTO DE RENDA (IRPF)", start=docs_idx)
        if irpf_idx != -1 and irpf_idx + 1 < len(lines):
            docs["irpf"] = lines[irpf_idx + 1]

    # ---- 14. CREDIT ANALYTICS ----
    credit_flags = {
        "data_atualizacao": "",
        "finalidade": "",
        "perfil_mobile": "",
        "cliente_premium": "",
        "perfil_luxo": "",
    }

    ca_idx = find_line("CREDIT ANALYTICS")
    if ca_idx != -1:
        for i in range(ca_idx, len(lines)):
            l = lines[i]
            if l.startswith("Data Atualização"):
                m = re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", " ".join(lines[i : i + 2]))
                if m:
                    credit_flags["data_atualizacao"] = m.group(0)
            elif l.startswith("Finalidade"):
                credit_flags["finalidade"] = " ".join(l.split()[1:])
            elif l.startswith("Perfil Mobile"):
                credit_flags["perfil_mobile"] = l.split()[-1]
            elif l.startswith("ClientePremium") or l.startswith("Cliente Premium"):
                credit_flags["cliente_premium"] = l.split()[-1]
            elif l.startswith("Perfil Luxo"):
                credit_flags["perfil_luxo"] = l.split()[-1]
            if re.match(r"[A-Za-z]+Internet", l):
                break

    # ---- 15. SCORES ----
    csb8_valor = ""
    csb8_label = ""
    csba_valor = ""
    csba_label = ""

    m_csb8 = re.search(r"SCORE\s*\(CSB8\).*?(\d{1,4})\s*/1000.*?Risco:\s*([A-ZÇÃÉÍÓÚ ]+)", full_text, re.DOTALL)
    if m_csb8:
        csb8_valor = m_csb8.group(1)
        csb8_label = f"Risco {m_csb8.group(2).title()}"

    m_csba = re.search(r"SCORE\s*\(CSBA\).*?(\d{1,4})\s*/1000.*?Risco:\s*([A-ZÇÃÉÍÓÚ ]+)", full_text, re.DOTALL)
    if m_csba:
        csba_valor = m_csba.group(1)
        csba_label = f"Risco {m_csba.group(2).title()}"

    # ---- 16. Monta dicionário final ----
    digits_cpf = re.sub(r"\D", "", cpf_raw or "")
    meta = {
        "data": meta_data,
        "protocolo": f"DT-CPF-{digits_cpf}" if digits_cpf else "",
        "solicitante": "ADMIN",
        "ref_cpf": format_cpf(cpf_raw),
    }

    data = {
        "meta": meta,
        "scores": {
            "csb8_valor": csb8_valor,
            "csb8_label": csb8_label,
            "csba_valor": csba_valor,
            "csba_label": csba_label,
            "renda_label": f"{renda_val} • Classe D",
            "renda_obs": "Faixa até R$ 1.000,00 • Poder aquisitivo muito baixo",
        },
        "identificacao": identificacao,
        "rf": rf,
        "escolaridade": escolaridade,
        "profissoes": profissoes,
        "rais": rais,
        "telefones": tels,
        "operadoras": operadoras,
        "emails": emails,
        "enderecos": enderecos,
        "parentes": parentes,
        "perfil_socio": perfil_socio,
        "mosaic": mosaic,
        "docs": docs,
        "credit_flags": credit_flags,
    }

    return data


@router.post("/mind7-to-delta-html", response_class=HTMLResponse)
async def mind7_to_delta_html(file: UploadFile = File(...)):
    """
    Endpoint que recebe o PDF do MIND-7 (CPF) e devolve o HTML já no padrão Delta Trace.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="O arquivo precisa ser um PDF.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="PDF vazio.")

    try:
        data = parse_mind7_pdf_to_data(file_bytes)
    except Exception as e:
        print(f"Erro no Parser: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao analisar PDF MIND-7: {str(e)}")

    # Garantia do meta.data
    data.setdefault("meta", {})
    data["meta"].setdefault("data", datetime.utcnow().strftime("%d/%m/%Y, %H:%M"))

    template = env.get_template("relatorio_pf_delta.html")
    html = template.render(**data)

    return HTMLResponse(content=html)