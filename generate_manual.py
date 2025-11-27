from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime

def generate_manual():
    filename = "MANUAL_TECNICO_DELTATRACE_V1.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # --- CAPA ---
    c.setFillColor(colors.HexColor("#10b981")) # Emerald Green
    c.rect(0, height - 100, width, 100, fill=True, stroke=False)
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "DELTATRACE INTELLIGENCE")
    c.setFont("Helvetica", 14)
    c.drawString(50, height - 85, "Manual Técnico de Entrega & Operação - v1.0")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 150, f"Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawString(50, height - 165, "Responsável Técnico: Gemini (Lead Architect)")

    # --- 1. ARQUITETURA ---
    y = height - 220
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "1. ARQUITETURA DO SISTEMA (CLOUD)")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "O sistema opera em arquitetura de microsserviços 100% na nuvem:")
    y -= 20
    c.drawString(60, y, "- FRONTEND (Visual): Vercel (Next.js 14 + React Flow)")
    y -= 15
    c.drawString(60, y, "- BACKEND (Cérebro): Render.com (Python FastAPI + Docker)")
    y -= 15
    c.drawString(60, y, "- DATABASE (Memória): Neo4j AuraDB (Graph Database)")
    y -= 15
    c.drawString(60, y, "- REPOSITÓRIO (Código): GitHub (Controle de Versão)")

    # --- 2. LINKS DE ACESSO ---
    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "2. LINKS DE ACESSO (PRODUÇÃO)")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(60, y, "PAINEL (Login): https://deltatrace-app.vercel.app")
    y -= 15
    c.drawString(60, y, "API (Backend): https://deltatrace-backend.onrender.com")
    y -= 15
    c.drawString(60, y, "GITHUB: https://github.com/deltatracebr-dot/deltatrace-backend")

    # --- 3. CREDENCIAIS MESTRAS ---
    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "3. CREDENCIAIS E SEGREDOS (CONFIDENCIAL)")
    y -= 20
    
    # Login App
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "ACESSO AO SISTEMA (Master Admin):")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "User: deltatracebr@gmail.com")
    c.drawString(250, y, "Pass: delta123")
    
    y -= 25
    # Neo4j
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "BANCO DE DADOS (Neo4j Aura):")
    y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(70, y, "URI: neo4j+s://9605d472.databases.neo4j.io")
    y -= 12
    c.drawString(70, y, "User: neo4j")
    y -= 12
    c.drawString(70, y, "Pass: KLXfQzeYpPTAKIEBRXxYp4wz8SYLEuU1UAsi83tlmks")

    # --- 4. PROCEDIMENTOS DE EMERGÊNCIA ---
    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "4. PROCEDIMENTOS DE RESET & MANUTENÇÃO")
    y -= 20
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "COMO LIMPAR O BANCO DE DADOS (RESET TOTAL):")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "1. Acesse o console do Neo4j Aura.")
    y -= 15
    c.drawString(70, y, "2. Execute a query: MATCH (n) DETACH DELETE n")
    y -= 15
    c.drawString(70, y, "3. Isso apaga todos os casos e nós. Use com cuidado.")

    y -= 25
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "COMO ATUALIZAR O SISTEMA:")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "1. Backend: Faça alterações locais -> 'git push origin main'. O Render atualiza sozinho.")
    y -= 15
    c.drawString(70, y, "2. Frontend: Use o comando 'vercel --prod' na pasta do projeto.")

    # --- 5. FUNCIONALIDADES ---
    y -= 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "5. FUNCIONALIDADES ENTREGUES (V1.0)")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(60, y, "[x] Ingestão de PDF (MIND7) com Regex Avançado (CPF, CNPJ, Placa, Phone)")
    y -= 15
    c.drawString(60, y, "[x] Grafo Interativo com detecção automática de vínculos")
    y -= 15
    c.drawString(60, y, "[x] Google Dorking Automático (Botão de Inteligência)")
    y -= 15
    c.drawString(60, y, "[x] Geração de Dossiê PDF automático")
    y -= 15
    c.drawString(60, y, "[x] Autenticação e Segurança (CORS Blindado)")

    c.save()
    print(f"PDF Gerado com sucesso: {filename}")

if __name__ == "__main__":
    generate_manual()
