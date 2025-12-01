from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from app.database import get_driver
import io
from datetime import datetime

def generate_pdf_report(case_id: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    driver = get_driver()
    
    # 1. Buscar Dados do Caso
    title = "RELATÓRIO DE INTELIGÊNCIA"
    targets = []
    phones = []
    addresses = []
    vehicles = []
    
    with driver.session() as session:
        # Busca Titulo do Caso
        res_case = session.run("MATCH (c:Case {id: $id}) RETURN c.title as title", id=case_id).single()
        if res_case:
            title = f"DOSSIÊ: {res_case['title'].upper()}"

        # Busca Entidades Conectadas
        result = session.run("""
            MATCH (c:Case {id: $id})-[*1..2]-(n)
            RETURN labels(n) as labels, properties(n) as props
        """, id=case_id)
        
        seen = set()
        
        for record in result:
            props = record["props"]
            labels = record["labels"]
            
            # --- SANITIZAÇÃO DE DADOS (SIGILO ABSOLUTO) ---
            # Removemos qualquer menção à fonte MIND-7 dos valores visíveis
            raw_val = props.get("label") or props.get("name") or props.get("number") or props.get("full_address") or "N/A"
            clean_val = str(raw_val).replace("MIND-7", "").replace("MIND7", "").strip()
            
            # Evita duplicatas
            if clean_val in seen: continue
            seen.add(clean_val)
            
            if "Person" in labels:
                targets.append(clean_val)
            elif "Phone" in labels:
                phones.append(clean_val)
            elif "Address" in labels:
                addresses.append(clean_val)
            elif "Vehicle" in labels or "PLACA" in clean_val:
                vehicles.append(clean_val)
            # Nota: Documentos PDF (nós de arquivo) são ignorados propositalmente no relatório final 
            # para não revelar o nome do arquivo original se ele contiver "MIND7".

    # --- DESENHAR O PDF ---
    
    # Cabeçalho
    c.setFillColor(colors.black)
    c.rect(0, height - 80, width, 80, fill=1)
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(30, height - 50, "DELTATRACE")
    
    c.setFont("Helvetica", 10)
    c.drawString(30, height - 65, "RELATÓRIO TÉCNICO DE INTELIGÊNCIA FORENSE")
    c.drawRightString(width - 30, height - 50, "CONFIDENCIAL")
    c.drawRightString(width - 30, height - 65, datetime.now().strftime("%d/%m/%Y %H:%M"))

    y = height - 120
    
    # Título do Caso
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(30, y, title)
    y -= 40

    # Função auxiliar para desenhar seções
    def draw_section(header, items, current_y):
        if not items: return current_y
        
        # Verifica quebra de página
        if current_y < 100:
            c.showPage()
            current_y = height - 50
        
        c.setFillColor(colors.darkblue)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(30, current_y, header)
        c.line(30, current_y - 5, width - 30, current_y - 5)
        current_y -= 25
        
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)
        
        for item in items:
            if current_y < 50:
                c.showPage()
                current_y = height - 50
            
            c.drawString(40, current_y, f"• {item}")
            current_y -= 15
            
        return current_y - 20

    # Renderizar Seções
    y = draw_section("ALVOS E VÍNCULOS IDENTIFICADOS", targets, y)
    y = draw_section("ENDEREÇOS LEVANTADOS", addresses, y)
    y = draw_section("TELEFONES E CONTATOS", phones, y)
    y = draw_section("VEÍCULOS E BENS", vehicles, y)

    # Rodapé
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.gray)
    c.drawString(30, 30, "Documento gerado automaticamente pelo sistema DeltaTrace. Uso exclusivo para fins de investigação.")
    c.drawRightString(width - 30, 30, "Página 1")

    c.save()
    buffer.seek(0)
    return buffer
