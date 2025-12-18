# D:\deltatrace_final\backend\app\main.py
# VERSÃO CORRIGIDA E COMPLETA - DELTATRACE OSINT COM IA

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from jinja2 import Template

# ==========================================
# CONFIGURAÇÕES DO SISTEMA
# ==========================================

# Configuração OpenAI (USE VARIÁVEIS DE AMBIENTE EM PRODUÇÃO!)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sua-chave-api-aqui")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4-turbo-preview"

app = FastAPI(title="DeltaTrace OSINT Engine", version="4.0")

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# MODELOS DE DADOS
# ==========================================

class Target(BaseModel):
    nome: str
    cpf: str = ""
    emails: List[str] = []
    telefones: List[str] = []
    usernames: List[str] = []

class OSINTRequest(BaseModel):
    target: Target

class NoteUpdate(BaseModel):
    note: str

# ==========================================
# ROTAS DE SAÚDE E DIAGNÓSTICO
# ==========================================

@app.get("/")
def root():
    return {"status": "DeltaTrace OSINT Online", "version": "4.0"}

@app.get("/health")
def health():
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "services": ["sherlock", "maigret", "holehe", "dorks", "ai"]
    }

# ==========================================
# FERRAMENTAS OSINT - FUNÇÕES PRINCIPAIS
# ==========================================

async def run_sherlock(username: str) -> List[Dict[str, Any]]:
    """Executa Sherlock para buscar username em redes sociais"""
    print(f"[SHERLOCK] Buscando: {username}")
    
    try:
        # Caminho para o Sherlock
        sherlock_path = r"D:\deltatrace_final\sherlock_tool"
        
        cmd = [
            sys.executable, "-m", "sherlock_project.sherlock",
            username,
            "--timeout", "5",
            "--print-found",
            "--no-color"
        ]
        
        result = subprocess.run(
            cmd,
            cwd=sherlock_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Processa a saída do Sherlock
            results = []
            for line in result.stdout.split('\n'):
                if line.strip() and '[+]' in line:
                    # Formato: [+] Site: https://site.com/username
                    parts = line.split(': ', 1)
                    if len(parts) == 2:
                        site = parts[0].replace('[+]', '').strip()
                        url = parts[1].strip()
                        results.append({
                            "tool": "Sherlock",
                            "site": site,
                            "url": url,
                            "status": "Encontrado"
                        })
            
            return results if results else [{"info": f"Nenhum resultado para {username}"}]
        else:
            return [{"error": result.stderr[:200]}]
            
    except subprocess.TimeoutExpired:
        return [{"error": "Timeout - Sherlock demorou muito"}]
    except Exception as e:
        return [{"error": f"Erro no Sherlock: {str(e)}"}]

async def run_maigret(username: str) -> List[Dict[str, Any]]:
    """Executa Maigret para busca profunda"""
    print(f"[MAIGRET] Buscando: {username}")
    
    try:
        cmd = [
            sys.executable, "-m", "maigret",
            username,
            "--timeout", "10",
            "--print-found",
            "--no-progressbar"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            results = []
            for line in result.stdout.split('\n'):
                if line.strip() and ' [+] ' in line:
                    # Formato: Site [+] https://site.com/username
                    parts = line.split(' [+] ', 1)
                    if len(parts) == 2:
                        site = parts[0].strip()
                        url = parts[1].strip()
                        results.append({
                            "tool": "Maigret",
                            "site": site,
                            "url": url,
                            "status": "Encontrado"
                        })
            
            return results if results else [{"info": f"Nenhum resultado no Maigret para {username}"}]
        else:
            return [{"error": result.stderr[:200]}]
            
    except subprocess.TimeoutExpired:
        return [{"error": "Timeout - Maigret demorou muito"}]
    except Exception as e:
        return [{"error": f"Erro no Maigret: {str(e)}"}]

async def run_holehe(email: str) -> List[Dict[str, Any]]:
    """Verifica email em vazamentos de dados"""
    print(f"[HOLEHE] Verificando: {email}")
    
    try:
        cmd = [
            sys.executable, "-m", "holehe",
            email,
            "--only-used",
            "--no-color"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            results = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and ('[+]' in line or '[-]' in line):
                    status = "Registrado" if '[+]' in line else "Não registrado"
                    site = line.split(':', 1)[0].replace('[+]', '').replace('[-]', '').strip()
                    results.append({
                        "tool": "Holehe",
                        "site": site,
                        "status": status,
                        "email": email
                    })
            
            return results if results else [{"info": f"Nenhum registro encontrado para {email}"}]
        else:
            # Fallback: links para verificação manual
            return [{
                "tool": "Holehe",
                "email": email,
                "status": "Verifique manualmente",
                "checks": [
                    {"site": "Have I Been Pwned", "url": f"https://haveibeenpwned.com/account/{email}"},
                    {"site": "Epieos", "url": f"https://epieos.com/?q={email}"}
                ]
            }]
            
    except Exception as e:
        return [{"error": f"Erro no Holehe: {str(e)}"}]

def run_dorks(query: str) -> List[Dict[str, Any]]:
    """Gera Google Dorks para busca"""
    print(f"[DORKS] Gerando para: {query}")
    
    dorks = []
    
    # Dorks para nome
    if " " in query:  # Provavelmente um nome
        name_dorks = [
            f'"{query}"',
            f'"{query}" site:.gov.br',
            f'"{query}" site:.jus.br',
            f'"{query}" filetype:pdf',
            f'"{query}" intitle:"processo"'
        ]
        
        for dork in name_dorks:
            google_url = f"https://www.google.com/search?q={dork.replace(' ', '+').replace('"', '%22')}"
            dorks.append({
                "tool": "Google Dorks",
                "site": "Google",
                "url": google_url,
                "query": dork,
                "status": "Dork gerado"
            })
    
    # Dorks para CPF (se parece com CPF)
    if re.match(r'\d{3}\.\d{3}\.\d{3}-\d{2}', query):
        cpf_dorks = [
            f'"{query}"',
            f'CPF {query}',
            f'{query.replace(".", "").replace("-", "")}',
            f'"{query}" filetype:pdf'
        ]
        
        for dork in cpf_dorks:
            google_url = f"https://www.google.com/search?q={dork.replace(' ', '+').replace('"', '%22')}"
            dorks.append({
                "tool": "Google Dorks",
                "site": "Google",
                "url": google_url,
                "query": dork,
                "status": "Dork gerado (CPF)"
            })
    
    return dorks if dorks else [{"info": "Nenhum dork gerado"}]

# ==========================================
# ROTAS OSINT QUE O FRONTEND ESPERA
# ==========================================

@app.post("/run-sherlock")
async def api_run_sherlock(request: OSINTRequest):
    """Executa Sherlock para os usernames do alvo"""
    try:
        results = []
        for username in request.target.usernames:
            sherlock_results = await run_sherlock(username)
            results.append({
                "username": username,
                "results": sherlock_results
            })
        
        return {
            "tool": "sherlock",
            "status": "completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Erro no Sherlock: {str(e)}")

@app.post("/run-maigret")
async def api_run_maigret(request: OSINTRequest):
    """Executa Maigret para os usernames do alvo"""
    try:
        results = []
        for username in request.target.usernames:
            maigret_results = await run_maigret(username)
            results.append({
                "username": username,
                "results": maigret_results
            })
        
        return {
            "tool": "maigret",
            "status": "completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Erro no Maigret: {str(e)}")

@app.post("/run-holehe")
async def api_run_holehe(request: OSINTRequest):
    """Executa Holehe para os emails do alvo"""
    try:
        results = []
        for email in request.target.emails:
            holehe_results = await run_holehe(email)
            results.append({
                "email": email,
                "results": holehe_results
            })
        
        return {
            "tool": "holehe",
            "status": "completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Erro no Holehe: {str(e)}")

@app.post("/run-dorks")
async def api_run_dorks(request: OSINTRequest):
    """Gera Google Dorks para o alvo"""
    try:
        dorks_list = []
        
        # Dorks para nome
        if request.target.nome:
            dorks_list.extend(run_dorks(request.target.nome))
        
        # Dorks para CPF
        if request.target.cpf:
            dorks_list.extend(run_dorks(request.target.cpf))
        
        # Dorks para combinações
        if request.target.nome and request.target.cpf:
            combo = f"{request.target.nome} {request.target.cpf}"
            dorks_list.extend(run_dorks(combo))
        
        return {
            "tool": "dorks",
            "status": "completed",
            "results": dorks_list,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Erro nos Dorks: {str(e)}")

# ==========================================
# ANÁLISE COM IA (OpenAI)
# ==========================================

async def generate_ai_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """Gera análise inteligente dos resultados OSINT"""
    try:
        # Prepara o prompt
        prompt = f"""Você é um analista especialista em OSINT da DeltaTrace.
        
Analise os seguintes dados de investigação e forneça:

1. RESUMO EXECUTIVO: Sintetize os principais achados
2. ANÁLISE POR FERRAMENTA: Comente os resultados de cada ferramenta
3. PARECER DE INTELIGÊNCIA: Avalie riscos e padrões
4. RECOMENDAÇÕES: Sugira próximos passos

DADOS PARA ANÁLISE:
{json.dumps(data, ensure_ascii=False, indent=2)}

Alvo: {data.get('target', {}).get('nome', 'Desconhecido')}
CPF: {data.get('target', {}).get('cpf', 'Não informado')}
Emails: {', '.join(data.get('target', {}).get('emails', []))}
Usernames: {', '.join(data.get('target', {}).get('usernames', []))}

Forneça a resposta em português, formato Markdown."""
        
        # Chama OpenAI
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Você é um analista OSINT profissional."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OPENAI_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
        
        analysis = result["choices"][0]["message"]["content"]
        
        return {
            "success": True,
            "analysis": analysis,
            "model": OPENAI_MODEL,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fallback": "Análise de IA indisponível. Verifique os resultados manualmente."
        }

@app.post("/analyze/ai-report")
async def api_ai_report(request: dict):
    """Gera relatório com análise de IA"""
    try:
        ai_result = await generate_ai_analysis(request)
        
        if ai_result["success"]:
            return {
                "success": True,
                "analysis": ai_result["analysis"],
                "metadata": {
                    "model": ai_result["model"],
                    "timestamp": ai_result["timestamp"]
                }
            }
        else:
            return {
                "success": False,
                "error": ai_result["error"],
                "fallback": ai_result["fallback"]
            }
    except Exception as e:
        raise HTTPException(500, detail=f"Erro na análise de IA: {str(e)}")

# ==========================================
# UPLOAD DE PDF E PROCESSAMENTO
# ==========================================

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Processa PDF MIND-7 e extrai dados para OSINT"""
    try:
        # Lê o conteúdo do PDF
        content = await file.read()
        
        # Salva temporariamente para análise
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Tenta extrair texto do PDF
            import pdfplumber
            extracted_text = ""
            
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
            
            # Extrai informações básicas (regex simples)
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', extracted_text)
            phones = re.findall(r'\(?\d{2}\)?[\s-]?\d{4,5}[\s-]?\d{4}', extracted_text)
            cpf_match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', extracted_text)
            cpf = cpf_match.group(0) if cpf_match else ""
            
            # Tenta extrair nome (primeira linha com mais de 3 palavras)
            nome = ""
            for line in extracted_text.split('\n'):
                line = line.strip()
                if len(line.split()) >= 3 and not any(word in line.lower() for word in ['email', 'telefone', 'cpf', 'rg', 'endereço']):
                    nome = line
                    break
            
            # Gera usernames a partir do nome
            usernames = []
            if nome:
                # Remove acentos e caracteres especiais
                nome_simple = re.sub(r'[^a-zA-Z0-9]', '', nome.lower())
                parts = nome.lower().split()
                if len(parts) >= 2:
                    usernames.append(f"{parts[0]}.{parts[-1]}")
                    usernames.append(f"{parts[0]}{parts[-1]}")
                    usernames.append(parts[0])
                    usernames.append(parts[-1])
            
            return {
                "success": True,
                "target": {
                    "nome": nome or file.filename.replace('.pdf', ''),
                    "cpf": cpf,
                    "emails": list(set(emails)),  # Remove duplicados
                    "telefones": list(set(phones)),  # Remove duplicados
                    "usernames": list(set(usernames))  # Remove duplicados
                },
                "metadata": {
                    "filename": file.filename,
                    "size": len(content),
                    "pages": len(extracted_text.split('\n')) // 50 + 1,
                    "extracted_text_preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
                }
            }
            
        except Exception as e:
            # Fallback se não conseguir extrair do PDF
            return {
                "success": True,
                "target": {
                    "nome": file.filename.replace('.pdf', ''),
                    "cpf": "",
                    "emails": [],
                    "telefones": [],
                    "usernames": []
                },
                "metadata": {
                    "filename": file.filename,
                    "size": len(content),
                    "error": f"PDF processado, mas extração limitada: {str(e)}"
                }
            }
            
        finally:
            # Limpa arquivo temporário
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        raise HTTPException(500, detail=f"Erro ao processar PDF: {str(e)}")

# ==========================================
# SCAN COMPLETO (TODAS AS FERRAMENTAS)
# ==========================================

@app.post("/analyze/full_scan")
async def full_scan_endpoint(request: OSINTRequest):
    """Executa todas as ferramentas OSINT para o alvo"""
    try:
        results = {}
        
        # Sherlock
        if request.target.usernames:
            sherlock_results = []
            for username in request.target.usernames:
                sherlock_data = await run_sherlock(username)
                sherlock_results.append({
                    "username": username,
                    "data": sherlock_data
                })
            results["sherlock"] = sherlock_results
        
        # Maigret
        if request.target.usernames:
            maigret_results = []
            for username in request.target.usernames:
                maigret_data = await run_maigret(username)
                maigret_results.append({
                    "username": username,
                    "data": maigret_data
                })
            results["maigret"] = maigret_results
        
        # Holehe
        if request.target.emails:
            holehe_results = []
            for email in request.target.emails:
                holehe_data = await run_holehe(email)
                holehe_results.append({
                    "email": email,
                    "data": holehe_data
                })
            results["holehe"] = holehe_results
        
        # Dorks
        dorks_data = run_dorks(request.target.nome)
        if request.target.cpf:
            dorks_data.extend(run_dorks(request.target.cpf))
        results["dorks"] = dorks_data
        
        return {
            "success": True,
            "target": request.target.dict(),
            "results": results,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tools": len(results),
                "has_data": any(len(data) > 0 for data in results.values())
            }
        }
        
    except Exception as e:
        raise HTTPException(500, detail=f"Erro no scan completo: {str(e)}")

# ==========================================
# EXPORTAÇÃO E RELATÓRIOS
# ==========================================

@app.post("/export/json")
async def export_json(request: dict):
    """Exporta dados em formato JSON"""
    return JSONResponse(
        content=request,
        headers={
            "Content-Disposition": f"attachment; filename=osint_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )

@app.post("/generate-html-report")
async def generate_html_report(request: dict):
    """Gera relatório HTML completo"""
    try:
        # Template HTML básico
        html_template = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Relatório OSINT - DeltaTrace</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .header { border-bottom: 2px solid #1a5fb4; padding-bottom: 20px; margin-bottom: 30px; }
                h1 { color: #1a5fb4; }
                .section { margin-bottom: 30px; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                th { background-color: #1a5fb4; color: white; }
                .ai-analysis { background-color: #f0f7ff; padding: 20px; border-radius: 8px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📋 Relatório OSINT - DeltaTrace</h1>
                <p>Gerado em: {{ timestamp }}</p>
                <p><strong>Alvo:</strong> {{ target.nome }}</p>
                {% if target.cpf %}<p><strong>CPF:</strong> {{ target.cpf }}</p>{% endif %}
            </div>
            
            {% if ai_analysis %}
            <div class="section">
                <h2>🧠 Análise por Inteligência Artificial</h2>
                <div class="ai-analysis">
                    <pre>{{ ai_analysis }}</pre>
                </div>
            </div>
            {% endif %}
            
            {% for tool, data in results.items() %}
            <div class="section">
                <h2>🔧 {{ tool|upper }}</h2>
                {% if data %}
                    {% if data is string %}
                    <p>{{ data }}</p>
                    {% elif data is iterable %}
                    <table>
                        <thead>
                            <tr>
                                <th>Site/Plataforma</th>
                                <th>URL/Informação</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in data %}
                            <tr>
                                <td>{{ item.site|default('N/A') }}</td>
                                <td>
                                    {% if item.url %}
                                    <a href="{{ item.url }}" target="_blank">{{ item.url|truncate(50) }}</a>
                                    {% else %}
                                    {{ item.info|default(item.error|default('N/A')) }}
                                    {% endif %}
                                </td>
                                <td>{{ item.status|default('N/A') }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% endif %}
                {% else %}
                <p>Nenhum resultado encontrado.</p>
                {% endif %}
            </div>
            {% endfor %}
            
            <div class="footer">
                <hr>
                <p><small>Gerado automaticamente por DeltaTrace OSINT Engine v4.0</small></p>
            </div>
        </body>
        </html>
        """
        
        # Renderiza o template
        template = Template(html_template)
        html_content = template.render(
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            target=request.get("target", {}),
            results=request.get("results", {}),
            ai_analysis=request.get("ai_analysis", "")
        )
        
        return {
            "success": True,
            "html": html_content,
            "filename": f"osint_report_{request.get('target', {}).get('nome', 'alvo').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        }
        
    except Exception as e:
        raise HTTPException(500, detail=f"Erro ao gerar relatório HTML: {str(e)}")

# ==========================================
# INICIALIZAÇÃO DO SERVIDOR
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)