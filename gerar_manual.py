from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime

def create_manual():
    filename = "MANUAL_TECNICO_DELTATRACE.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    w, h = A4
    
    # --- CAPA ---
    c.setFillColor(colors.HexColor("#0f172a")) # Slate 900
    c.rect(0, 0, w, h, fill=True)
    
    c.setFillColor(colors.HexColor("#10b981")) # Emerald
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(w/2, h - 300, "DELTATRACE")
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 16)
    c.drawCentredString(w/2, h - 330, "INTELLIGENCE CORE v1.0")
    
    c.setFont("Helvetica", 10)
    c.drawCentredString(w/2, h - 500, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawCentredString(w/2, h - 515, "Status: OPERACIONAL NA NUVEM")
    
    c.showPage()
    
    # --- PÁGINA 1: ACESSOS ---
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h - 50, "1. LINKS DE ACESSO (PRODUÇÃO)")
    
    c.setFont("Helvetica", 12)
    y = h - 80
    c.drawString(50, y, "• Frontend (Painel): https://deltatrace-app.vercel.app")
    y -= 20
    c.drawString(50, y, "• Backend (API): https://deltatrace-backend.onrender.com")
    y -= 20
    c.drawString(50, y, "• Repositório: https://github.com/deltatracebr-dot/deltatrace-backend")
    
    y -= 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "2. CREDENCIAIS MESTRAS")
    y -= 30
    
    # Login App
    c.setFillColor(colors.HexColor("#0f172a"))
    c.rect(40, y-60, 500, 70, fill=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y-15, "LOGIN DO SISTEMA (MASTER):")
    c.setFont("Helvetica", 12)
    c.drawString(50, y-35, "User: deltatracebr@gmail.com")
    c.drawString(50, y-55, "Pass: delta123")
    
    y -= 90
    # Neo4j
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "BANCO DE DADOS (Neo4j AuraDB):")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "URI: neo4j+s://9605d472.databases.neo4j.io")
    y -= 15
    c.drawString(50, y, "User: neo4j")
    y -= 15
    c.drawString(50, y, "Pass: KLXfQzeYpPTAKIEBRXxYp4wz8SYLEuU1UAsi83tlmks")
    
    # --- PÁGINA 2: MANUTENÇÃO ---
    y -= 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "3. PROCEDIMENTOS DE MANUTENÇÃO")
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "COMO RESETAR O BANCO DE DADOS:")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "1. Acesse o Console do Neo4j Aura.")
    y -= 15
    c.drawString(50, y, "2. Abra a aba 'Query'.")
    y -= 15
    c.drawString(50, y, "3. Execute: MATCH (n) DETACH DELETE n")
    
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "COMO ATUALIZAR O CÓDIGO:")
    y -= 15
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "BACKEND: Altere o código em 'backend/', faça commit e 'git push'. O Render atualiza auto.")
    y -= 15
    c.drawString(50, y, "FRONTEND: Altere em 'frontend/' e rode 'vercel --prod' no terminal.")

    c.save()

if __name__ == "__main__":
    create_manual()
