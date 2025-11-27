from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime

def generate_manual():
    filename = "MANUAL_TECNICO_DELTATRACE.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # --- CAPA ---
    c.setFillColor(colors.HexColor("#10b981"))
    c.rect(0, height - 100, width, 100, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "DELTATRACE INTELLIGENCE")
    c.setFont("Helvetica", 14)
    c.drawString(50, height - 85, "Manual Técnico & Credenciais - v1.0")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 150, f"Backup Realizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    # --- CONTEÚDO ---
    y = height - 200
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "1. ACESSOS E LINKS (PRODUÇÃO)")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(60, y, "PAINEL (Frontend): https://deltatrace-app.vercel.app")
    y -= 15
    c.drawString(60, y, "API (Backend): https://deltatrace-backend.onrender.com")
    y -= 15
    c.drawString(60, y, "REPOSITÓRIO: https://github.com/deltatracebr-dot/deltatrace-backend")

    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "2. CREDENCIAIS MESTRAS")
    y -= 20
    c.drawString(60, y, "LOGIN DO SISTEMA:")
    y -= 15
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(70, y, "User: deltatracebr@gmail.com")
    y -= 15
    c.drawString(70, y, "Pass: delta123")
    
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "BANCO DE DADOS (Neo4j Aura):")
    y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(70, y, "URI: neo4j+s://9605d472.databases.neo4j.io")
    y -= 15
    c.drawString(70, y, "User: neo4j")
    y -= 15
    c.drawString(70, y, "Pass: KLXfQzeYpPTAKIEBRXxYp4wz8SYLEuU1UAsi83tlmks")

    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "3. INSTRUÇÕES DE MANUTENÇÃO")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(60, y, "- O código fonte está salvo neste ZIP.")
    y -= 15
    c.drawString(60, y, "- Para rodar localmente: python -m uvicorn app.main:app --reload")
    y -= 15
    c.drawString(60, y, "- Para atualizar a nuvem: Faça alterações e rode 'git push origin main'.")

    c.save()

if __name__ == "__main__":
    generate_manual()
