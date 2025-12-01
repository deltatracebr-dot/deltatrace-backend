import re
from typing import List
from app.schemas import PhoneResult, AddressResult

class Mind7Extractor:
    def __init__(self, raw_text: str, target_name: str):
        self.text = raw_text
        self.target_name = target_name.upper() if target_name else "ALVO"
        print(f"--- DEBUG TEXTO PDF ({len(raw_text)} chars) ---\n{raw_text[:200]}...")

    def extract_phones(self) -> List[PhoneResult]:
        results = []
        raw_matches = re.findall(r'\b\d{10,11}\b', self.text)
        fmt_matches = re.findall(r'\(\d{2}\)\s?\d{4,5}[-\s]?\d{4}', self.text)
        all_candidates = list(set(raw_matches + fmt_matches))
        print(f"--- DEBUG PHONES ENCONTRADOS: {len(all_candidates)}")

        for ph in all_candidates:
            clean = re.sub(r'\D', '', ph)
            if len(clean) == 11 and clean.startswith('0'): continue
            if len(clean) > 11: continue

            # ANÁLISE DE CONTEXTO (NOVO)
            # Verifica se o nome do alvo está PERTO deste telefone no texto
            escaped_ph = re.escape(ph)
            context_window = re.search(f".{{0,200}}{escaped_ph}.{{0,200}}", self.text, re.DOTALL | re.IGNORECASE)
            is_linked = False
            owner = "TERCEIRO / DESCONHECIDO"
            
            if context_window:
                snippet = context_window.group(0).upper()
                if self.target_name in snippet:
                    is_linked = True
                    owner = f"VINCULADO A {self.target_name}"
                
                # Tenta extrair o nome do dono original no snippet
                # Procura por "NOME" ou "TITULAR" seguido de letras maiúsculas
                owner_match = re.search(r'(?:NOME|TITULAR)[:\s]+([A-Z\s]+)', snippet)
                if owner_match:
                    possible_owner = owner_match.group(1).strip()
                    if len(possible_owner) > 3 and possible_owner != "TELEFONES":
                        owner = possible_owner

            # SCORE DE INTELIGÊNCIA
            score = 0
            if is_linked: score = 90 # Alta relevância (aparece junto com o alvo)
            elif "MÃE" in self.text or "PAI" in self.text: score = 70 # Contexto familiar
            else: score = 40 # Baixa relevância (apenas citado)

            # SALVA SE FOR RELEVANTE
            # Antes cortávamos < 50. Agora aceitamos >= 40 se tiver contexto.
            if score >= 40:
                results.append(PhoneResult(
                    raw_text="...", 
                    source_pdf="MIND7_AUTO",
                    number=ph,
                    registered_owner=owner,
                    classification="Investigar" if score < 80 else "Vínculo Forte",
                    confidence_score=score
                ))
            
        # PLACAS
        placas = re.findall(r'\b([A-Z]{3}[0-9][0-9A-Z][0-9]{2})\b', self.text)
        for p in placas:
            results.append(PhoneResult(
                raw_text="VEICULO", 
                source_pdf="MIND7_AUTO",
                number=f"PLACA {p}", 
                registered_owner="VEICULO",
                classification="Veículo",
                confidence_score=90
            ))

        return results

    def extract_addresses(self) -> List[AddressResult]:
        results = []
        addr_regex = r'\b((?:RUA|R\.|R|AV|AV\.|AVENIDA|ALAMEDA|TRAVESSA|RODOVIA|ESTRADA|PRACA)\s+[A-Z\s0-9]+?,?\s*\d+)'
        matches = re.findall(addr_regex, self.text, re.IGNORECASE)
        processed = set()
        for m in matches:
            full = m.strip().upper()
            if full in processed or len(full) < 6: continue
            processed.add(full)
            results.append(AddressResult(
                raw_text="...",
                source_pdf="MIND7_AUTO",
                full_address=full,
                associated_names=[],
                is_family_hq=False,
                match_count=1
            ))
        return results
