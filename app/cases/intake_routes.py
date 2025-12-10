from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.database import get_driver
import uuid

router = APIRouter(prefix="/cases", tags=["cases-intake"])

# ---------- MODELOS DE ENTRADA ----------
class PersonPayload(BaseModel):
    name: Optional[str] = Field(None, description="Nome completo")
    email: Optional[str] = None
    phone: Optional[str] = None
    document: Optional[str] = Field(
        None,
        description="CPF/CNPJ ou outro identificador"
    )
    # Do ChatGPT (flexibilidade) + Gemini (simplicidade)
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Campos adicionais vindos do formulário (endereços, redes sociais, etc.)"
    )

class CaseIntakePayload(BaseModel):
    case_id: Optional[str] = Field(
        None,
        description="ID lógico do caso. Se não vier, o backend gera."
    )
    source: Optional[str] = Field(
        default="google_forms",
        description="Origem do caso (ex.: google_forms, manual, api)"
    )
    title: Optional[str] = Field(
        None,
        description="Título curto do caso (opcional)"
    )
    description: Optional[str] = Field(
        None,
        description="Descrição/resumo do caso"
    )
    status: Optional[str] = Field(
        default="Novo",
        description="Status inicial do caso"
    )

    solicitante: Optional[PersonPayload] = Field(
        None,
        description="Dados de quem está solicitando a investigação"
    )
    investigado: Optional[PersonPayload] = Field(
        None,
        description="Pessoa/entidade alvo da investigação"
    )

    labels: List[str] = Field(
        default_factory=list,
        description="Tags do caso (ex.: roubo, fraude, OSINT)"
    )

    raw_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Payload bruto vindo do formulário (para auditoria)"
    )

# ---------- FUNÇÃO AUXILIAR ----------
def _ensure_driver():
    driver = get_driver()
    if not driver:
        raise HTTPException(
            status_code=500,
            detail="Banco de dados Neo4j não está conectado (driver vazio)."
        )
    return driver

def _generate_case_id(driver) -> str:
    """
    Gera ID no formato: DT-ANO-SEQUENCIAL (ex: DT-2025-001)
    Busca no banco qual o último sequencial para o ano atual.
    """
    year = datetime.now().year
    prefix = f"DT-{year}-"
    
    try:
        with driver.session() as session:
            # Busca o maior ID que começa com o prefixo do ano
            result = session.run("""
                MATCH (c:Case)
                WHERE c.id STARTS WITH $prefix
                RETURN c.id as id
                ORDER BY c.id DESC
                LIMIT 1
            """, prefix=prefix).single()
            
            if result:
                last_id = result["id"] # Ex: DT-2025-042
                # Extrai o número final
                parts = last_id.split("-")
                if len(parts) == 3 and parts[2].isdigit():
                    next_seq = int(parts[2]) + 1
                    return f"{prefix}{next_seq:03d}"
            
            # Se não achou nada ou erro no parse, começa do 001
            return f"{prefix}001"
            
    except Exception as e:
        print(f"Erro ao gerar ID sequencial: {e}. Usando fallback UUID.")
        # Fallback seguro se der erro no banco
        return f"DT-{year}-{uuid.uuid4().hex[:6].upper()}"

# ---------- ROTA PRINCIPAL DE INTAKE ----------
@router.post("/intake")
def create_case_from_intake(payload: CaseIntakePayload):
    """
    Endpoint oficial para CRIAR/REGISTRAR um caso a partir de um intake externo (ex.: n8n + Google Forms).
    """
    driver = _ensure_driver()

    # Gera case_id profissional se não vier do n8n
    # Nota: Se o n8n já mandar o ID (recomendado), usamos ele.
    if payload.case_id:
        case_id = payload.case_id
    else:
        case_id = _generate_case_id(driver)
        
    now_iso = datetime.utcnow().isoformat()

    with driver.session() as session:
        # 1) Garante o nó Case
        session.run(
            """
            MERGE (c:Case {id: $case_id})
            ON CREATE SET
                c.created_at = datetime($now_iso),
                c.status      = $status,
                c.source      = $source,
                c.title       = coalesce($title, $case_id),
                c.description = $description
            ON MATCH SET
                c.updated_at  = datetime($now_iso),
                c.status      = $status,
                c.source      = $source,
                c.title       = coalesce($title, c.title),
                c.description = coalesce($description, c.description)
            """,
            case_id=case_id,
            now_iso=now_iso,
            status=payload.status,
            source=payload.source,
            title=payload.title,
            description=payload.description,
        )

        # 2) Seta labels/tags do caso (se vieram)
        if payload.labels:
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                SET c.labels_osint = $labels
                """,
                case_id=case_id,
                labels=payload.labels,
            )

        # 3) Guarda payload bruto para auditoria
        if payload.raw_payload:
            # Neo4j não guarda dict aninhado complexo direto, converte para string se necessário
            # Aqui assumimos que o driver lida com map simples ou serializamos
            import json
            raw_str = json.dumps(payload.raw_payload, default=str)
            session.run(
                """
                MATCH (c:Case {id: $case_id})
                SET c.raw_intake = $raw_str
                """,
                case_id=case_id,
                raw_str=raw_str,
            )

        # 4) Cria Solicitante (se veio)
        if payload.solicitante and (payload.solicitante.name or payload.solicitante.email):
            s = payload.solicitante
            solicitante_key = s.email or s.document or f"{s.name}_{case_id}" # Chave única melhorada

            session.run(
                """
                MERGE (p:Person {external_ref: $solicitante_key})
                ON CREATE SET
                    p.name       = $name,
                    p.email      = $email,
                    p.phone      = $phone,
                    p.document   = $document,
                    p.role       = "Solicitante",
                    p.created_at = datetime($now_iso)
                ON MATCH SET
                    p.updated_at = datetime($now_iso)
                """,
                solicitante_key=solicitante_key,
                name=s.name, email=s.email, phone=s.phone, document=s.document, now_iso=now_iso
            )
            # Liga ao caso
            session.run(
                "MATCH (c:Case {id: $cid}), (p:Person {external_ref: $skey}) MERGE (c)-[:REQUESTED_BY]->(p)",
                cid=case_id, skey=solicitante_key
            )

        # 5) Cria Investigado (se veio)
        if payload.investigado and (payload.investigado.name or payload.investigado.document):
            t = payload.investigado
            # Investigado chave: Documento é o melhor, se não, usa nome (cuidado com homônimos)
            target_key = t.document or f"{t.name}_TARGET_{case_id}"

            session.run(
                """
                MERGE (p:Person {external_ref: $target_key})
                ON CREATE SET
                    p.name       = $name,
                    p.email      = $email,
                    p.phone      = $phone,
                    p.document   = $document,
                    p.role       = "Investigado",
                    p.created_at = datetime($now_iso)
                ON MATCH SET
                    p.updated_at = datetime($now_iso)
                """,
                target_key=target_key,
                name=t.name, email=t.email, phone=t.phone, document=t.document, now_iso=now_iso
            )
            # Liga ao caso
            session.run(
                "MATCH (c:Case {id: $cid}), (p:Person {external_ref: $tkey}) MERGE (c)-[:TARGET]->(p)",
                cid=case_id, tkey=target_key
            )

    return {
        "status": "ok",
        "case_id": case_id,
        "message": "Caso registrado no Neo4j com sucesso.",
        "generated_id": (not payload.case_id) # Flag para saber se foi gerado
    }
