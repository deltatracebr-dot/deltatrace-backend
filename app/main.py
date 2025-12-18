from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import subprocess
import os
import sys
import json
import asyncio
import httpx
import traceback
import io
import re
from datetime import datetime
from jinja2 import Template

# --- PATCH OBRIGATÓRIO PARA WINDOWS ---
# Isso resolve o "NotImplementedError" e faz o Sherlock rodar
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- IMPORTS DE RELATÓRIO PDF ---
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
except ImportError:
    print("[AVISO] ReportLab não instalado. Geração de PDF nativo pode falhar.")

# --- IMPORTS DO SEU PROJETO ---
try:
    from app.reports.routes import router as reports_router
    from app.cases import intake_routes
    from app.cases import routes as cases_routes
    from app.services.report_generator import generate_pdf_report
    from app.services.extractor import Mind7Extractor
    from app.database import verify_connection, get_driver
    from app.schemas import InvestigationReport, PersonResult
except ImportError as e:
    print(f"[AVISO] Módulos locais parciais ou ausentes: {e}. Usando modo de compatibilidade.")
    reports_router = FastAPI().router
    intake_routes = FastAPI().router
    cases_routes = FastAPI().router
    def verify_connection(): pass
    def get_driver(): return None
    # Definições dummy caso o schema real falhe
    class PersonResult(BaseModel):
        name: str
        source_pdf: Optional[str] = None
        raw_text: Optional[str] = None
        cpf: Optional[str] = None
        surnames: List[str] = []
    class InvestigationReport(BaseModel):
        target: PersonResult
        phones: List[Any]
        addresses: List[Any]
        emails: List[Any] = [] # Adicionado para evitar erro de frontend

# --- IMPORTS DE BUSCA ---
try:
    from googlesearch import search as google_search
except ImportError:
    google_search = None

app = FastAPI(title="DeltaTrace Intelligence - All-Source Engine")

# ==========================================
# CONFIGURAÇÃO DE CORS (ATUALIZADA)
# ==========================================
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://deltatrace-app.vercel.app",      # Antigo
    "https://deltatrace-frontend.vercel.app", # NOVO (Onde seu site está agora)
    "*"                                         # Permite tudo (Para garantir que funcione agora)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Forçando permissão total temporariamente para eliminar erros
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração OpenAI
OPENAI_API_KEY = "sk-proj-..."
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4-turbo-preview"

# --- ROTAS ORIGINAIS ---
app.include_router(cases_routes.router, prefix="/cases", tags=["cases"])
app.include_router(intake_routes.router)
app.include_router(reports_router, prefix="/reports", tags=["reports"])

@app.on_event("startup")
def startup_event():
    print("--> [SYSTEM] Verificando conexão com Banco de Dados...")
    try:
        verify_connection()
    except:
        print("[AVISO] Banco de dados offline ou não configurado.")

@app.get("/")
def read_root():
    return {"status": "DeltaTrace Intelligence Online", "version": "5.6 - HTML Export"}

@app.get("/health")
async def health_check():
    return {"status": "online", "timestamp": datetime.now().isoformat()}

# ==========================================
# 1. FERRAMENTAS OSINT (VERSÃO SÍNCRONA PARA WINDOWS)
# ==========================================

def run_tool_sync(cmd_list):
    """Executa comando de forma síncrona para evitar erro asyncio no Windows"""
    print(f"[DEBUG COMANDO] {' '.join(cmd_list)}")
    try:
        # encoding latin-1 evita erro de caractere estranho no console
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            encoding='latin-1',
            errors='ignore',
            timeout=90 
        )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "", "Timeout excedido na execução da ferramenta."
    except Exception as e:
        return "", str(e)

async def run_sherlock(username: str):
    print(f"--> [SHERLOCK] Buscando: {username}")
    cmd = [sys.executable, "-m", "sherlock_project", username, "--print-found", "--timeout", "15", "--no-color"]
    
    stdout, stderr = await asyncio.to_thread(run_tool_sync, cmd)

    if stdout: print(f"[SHERLOCK STDOUT]: {stdout[:200]}...")
    if stderr and "Update" not in stderr:
        print(f"[SHERLOCK STDERR]: {stderr[:500]}")

    found = []
    if stdout:
        for line in stdout.split('\n'):
            if "[+]" in line and "http" in line:
                try:
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        url = parts[1].strip()
                        site_name = url.split("//")[-1].split("/")[0].replace("www.", "")
                        found.append({"tool": "Sherlock", "site": site_name, "url": url})
                except: continue
    
    if not found:
        return [{"info": "Nenhum resultado encontrado no Sherlock."}]
        
    return found

async def run_maigret(username: str):
    print(f"--> [MAIGRET] Deep Scan: {username}")
    cmd = [sys.executable, "-m", "maigret", username, "--timeout", "40", "--no-progressbar", "--print-not-found"]
    
    stdout, stderr = await asyncio.to_thread(run_tool_sync, cmd)
    
    if stderr: print(f"[MAIGRET STDERR]: {stderr[:500]}")

    results = []
    if stdout:
        for line in stdout.split('\n'):
            if "http" in line and username in line:
                results.append({"tool": "Maigret", "raw_data": line.strip()})
    
    if not results:
            return [{"info": "Nenhum resultado no Maigret."}]

    return results

async def run_holehe(email: str):
    print(f"--> [HOLEHE] Verificando: {email}")
    cmd = [sys.executable, "-m", "holehe", email, "--only-used", "--no-color", "--timeout", "10"]
    
    stdout, stderr = await asyncio.to_thread(run_tool_sync, cmd)

    if stderr: print(f"[HOLEHE STDERR]: {stderr[:200]}")
    
    results = []
    if stdout:
        for line in stdout.split('\n'):
            if "[+]" in line:
                site = line.split(":")[-1].strip() if ":" in line else line.replace("[+]", "").strip()
                results.append({"tool": "Holehe", "site": site, "status": "Cadastrado"})
    
    if results: return results

    return [
        {
            "tool": "Holehe",
            "email": email,
            "status": "Verificação Manual Recomendada:",
            "checks": [
                {"site": "Have I Been Pwned", "url": f"https://haveibeenpwned.com/account/{email}"},
                {"site": "Epieos", "url": f"https://epieos.com/?q={email}"}
            ]
        }
    ]

def run_dorks(query: str):
    print(f"--> [DORKS FULL MODE] Buscando: {query}")

    # Lista OSINT profissional (15+)
    dorks = [
        f'"{query}"',
        f'"{query}" CPF',
        f'"{query}" RG',
        f'"{query}" processo',
        f'site:jusbrasil.com.br "{query}"',
        f'site:escavador.com "{query}"',
        f'site:linkedin.com/in "{query}"',
        f'site:facebook.com "{query}"',
        f'site:instagram.com "{query}"',
        f'site:twitter.com "{query}"',
        f'site:x.com "{query}"',
        f'site:github.com "{query}"',
        f'site:medium.com "{query}"',
        f'site:academia.edu "{query}"',
        f'site:docplayer.com.br "{query}"',
        f'"{query}" filetype:pdf',
        f'"{query}" filetype:doc',
        f'"{query}" filetype:xls',
        f'"{query}" currículo',
        f'"{query}" endereço'
    ]

    results = []

    if google_search:
        for dork in dorks:
            try:
                for url in google_search(
                    dork,
                    num_results=8,
                    lang="pt",
                ):
                    domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                    results.append({
                        "tool": "Dorks",
                        "site": domain,
                        "url": url,
                        "query": dork
                    })
            except Exception as e:
                print(f"[DORK ERROR] {dork}: {e}")
                continue

    # Deduplicação
    seen = set()
    final = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            final.append(r)

    # Fallback inteligente (nunca menos que 5)
    if len(final) < 5:
        fallback = [
            {"tool": "Dorks", "site": "JusBrasil", "url": f"https://jusbrasil.com.br/busca?q={query.replace(' ', '+')}"},
            {"tool": "Dorks", "site": "Escavador", "url": f"https://www.escavador.com/busca?qo=p&q={query.replace(' ', '+')}"},
            {"tool": "Dorks", "site": "Google Geral", "url": f"https://www.google.com/search?q={query.replace(' ', '+')}"},
            {"tool": "Dorks", "site": "Google PDFs", "url": f"https://www.google.com/search?q={query.replace(' ', '+')}+filetype:pdf"},
            {"tool": "Dorks", "site": "LinkedIn", "url": f"https://www.google.com/search?q=site:linkedin.com+{query.replace(' ', '+')}"}
        ]
        final.extend(fallback)

    return final

# ==========================================
# 2. ROTAS DA API
# ==========================================

@app.post("/analyze/sherlock")
async def api_sherlock(username: str = Form(...)):
    results = await run_sherlock(username)
    return {"target": username, "results": results}

@app.post("/analyze/maigret")
async def api_maigret(username: str = Form(...)):
    results = await run_maigret(username)
    return {"target": username, "results": results}

@app.post("/analyze/holehe")
async def api_holehe(email: str = Form(...)):
    results = await run_holehe(email)
    return {"target": email, "results": results}

@app.post("/analyze/dorks")
def api_dorks(term: str = Form(...)):
    results = run_dorks(term)
    return {"target": term, "results": results}

@app.post("/analyze/full_scan")
async def full_scan(
    name: str = Form(None), 
    cpf: str = Form(None), 
    email: str = Form(None), 
    username: str = Form(None)
):
    consolidated_report = []
    if username:
        res = await run_sherlock(username)
        if res: consolidated_report.extend(res)
    if email:
        res = await run_holehe(email)
        if res: consolidated_report.extend(res)
    if name:
        res = run_dorks(name)
        if res: consolidated_report.extend(res)

    full_report = {
        "metadata": {"exportedAt": datetime.now().isoformat(), "target": name or "Desconhecido"},
        "results": consolidated_report
    }
    return {
        "status": "Scan Finalizado", 
        "total_results": len(consolidated_report), 
        "report_data": consolidated_report,
        "full_report": full_report
    }

# --- ROTA DE UPLOAD DE PDF (CORRIGIDA - EVITA ERRO 500) ---
@app.post("/analyze/pdf", response_model=InvestigationReport)
async def analyze_pdf_root(
    file: UploadFile = File(...), 
    target_name: Optional[str] = Form(None)
):
    print(f"--> [UPLOAD-PDF] Recebido: {file.filename}")
    
    final_name = target_name if target_name else file.filename.replace(".pdf", "")
    emails_data = []
    phones_data = []
    cpf_val = "Não Identificado"
    
    try:
        content = await file.read()
        try:
            from app.reports.routes import parse_mind7_pdf_to_data
            parsed = parse_mind7_pdf_to_data(content)
            
            if parsed.get('identificacao', {}).get('nome'):
                final_name = parsed['identificacao']['nome']
            if parsed.get('meta', {}).get('ref_cpf'):
                cpf_val = parsed['meta']['ref_cpf']
            
            # Populando E-mails
            if parsed.get('emails'):
                for item in parsed['emails']:
                    email_val = item['email'] if isinstance(item, dict) else str(item)
                    emails_data.append({
                        "email": email_val,
                        "raw_text": email_val,
                        "source_pdf": file.filename,
                        "registered_owner": "Desconhecido",
                        "classification": "Pessoal",
                        "confidence_score": 1.0
                    })

            # Populando Telefones
            if parsed.get('telefones'):
                for item in parsed['telefones']:
                    phone_val = item['numero'] if isinstance(item, dict) else str(item)
                    carrier_val = item.get('obs', '') if isinstance(item, dict) else ""
                    phones_data.append({
                        "number": phone_val,
                        "carrier": carrier_val,
                        "raw_text": phone_val,
                        "source_pdf": file.filename,
                        "registered_owner": "Desconhecido",
                        "classification": "Celular/Fixo",
                        "confidence_score": 1.0
                    })
        except Exception as e:
            print(f"Erro no parser interno: {e}. Usando fallback.")
            # Fallback Regex básico
            text = content.decode('latin-1', errors='ignore')
            email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            for em in list(set(email_matches)):
                emails_data.append({"email": em, "raw_text": em, "source_pdf": file.filename, "registered_owner": "Auto", "classification": "Extraído", "confidence_score": 0.5})

    except Exception as e:
        print(f"[PDF ERROR] Erro fatal leitura: {e}")

    # RETORNO BLINDADO (Com campos obrigatórios para não dar 500)
    return InvestigationReport(
        target=PersonResult(
            name=final_name.upper(),
            source_pdf=file.filename,
            raw_text="Processado", # Campo obrigatório adicionado
            cpf=cpf_val,
            surnames=[] # Campo obrigatório adicionado
        ),
        phones=phones_data,
        emails=emails_data, 
        addresses=[] 
    )

# --- NOVA ROTA: GERAR RELATÓRIO HTML (DOSSIER STYLE) ---
@app.post("/generate-html-report")
async def generate_html_report(data: dict):
    print("--> Gerando Dossier HTML...")
    
    target = data.get('target', {})
    results = data.get('results', [])
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Dossier Delta Trace - {target.get('name', 'Alvo')}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #f4f4f4; padding: 40px; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 40px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; border-bottom: 3px solid #0f2a4a; padding-bottom: 20px; margin-bottom: 30px; }}
            .header h1 {{ color: #0f2a4a; margin: 0; font-size: 28px; }}
            .header p {{ color: #666; margin-top: 5px; }}
            .card {{ background: #e6f0fa; border-left: 5px solid #0f2a4a; padding: 20px; margin-bottom: 30px; }}
            .card h3 {{ margin-top: 0; color: #0f2a4a; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ background: #0f2a4a; color: #fff; padding: 10px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; font-size: 14px; }}
            tr:nth-child(even) {{ background: #f9f9f9; }}
            .tag {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; color: white; }}
            .tag.sherlock {{ background: #28a745; }}
            .tag.maigret {{ background: #6f42c1; }}
            .tag.dorks {{ background: #dc3545; }}
            .tag.holehe {{ background: #ffc107; color: black; }}
            a {{ color: #0056b3; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>DOSSIER DE INTELIGÊNCIA DIGITAL</h1>
                <p>DELTA DATA INTELLIGENCE • {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
            
            <div class="card">
                <h3>DADOS DO ALVO</h3>
                <p><b>NOME:</b> {target.get('name', 'N/A')}</p>
                <p><b>CPF:</b> {target.get('cpf', 'N/A')}</p>
                <p><b>TOTAL RESULTADOS:</b> {len(results)}</p>
            </div>
            
            <h3>RESULTADOS DETALHADOS</h3>
            <table>
                <thead>
                    <tr>
                        <th width="15%">Ferramenta</th>
                        <th width="25%">Fonte/Site</th>
                        <th>Dados / Link</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for item in results:
        tool = item.get('tool', 'Info').lower()
        tool_cls = tool if tool in ['sherlock', 'maigret', 'dorks', 'holehe'] else 'default'
        
        link = item.get('url', '')
        display_link = link
        if link.startswith('http'):
            display_link = f'<a href="{link}" target="_blank">{link}</a>'
            
        html_content += f"""
            <tr>
                <td><span class="tag {tool_cls}">{item.get('tool')}</span></td>
                <td>{item.get('site', 'N/A')}</td>
                <td>{display_link} <br/> <small style='color:gray'>{item.get('raw_data','')}</small></td>
            </tr>
        """
        
    html_content += """
                </tbody>
            </table>
            
            <div style="margin-top: 50px; text-align: center; color: #999; font-size: 12px;">
                <p>Relatório gerado automaticamente por DeltaTrace OSINT Engine</p>
                <p>Uso estritamente confidencial.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return {"html": html_content}

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("DeltaTrace OSINT Backend - V5.5 STABLE + HTML EXPORT")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8080)