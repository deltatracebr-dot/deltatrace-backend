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

            results.append(PhoneResult(
                raw_text="...", 
                source_pdf="MIND7_AUTO",
                number=ph,
                registered_owner="EXTRAÍDO VIA UPLOAD",
                classification="Investigar",
                confidence_score=60
            ))
            
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
        # REGEX V4: Aceita "R ", "R.", "AV " e ignora case
        # Estrutura: (Prefixo) + (Nome da Rua) + (Número)
        addr_regex = r'\b((?:RUA|R\.|R|AV|AV\.|AVENIDA|ALAMEDA|TRAVESSA|RODOVIA|ESTRADA|PRACA)\s+[A-Z\s0-9]+?,?\s*\d+)'
        
        matches = re.findall(addr_regex, self.text, re.IGNORECASE)
        print(f"--- DEBUG ENDEREÇOS ENCONTRADOS: {len(matches)}")

        processed = set()
        for m in matches:
            full = m.strip().upper()
            # Filtra falsos positivos muito curtos (ex: "R 1")
            if full in processed or len(full) < 6: continue
            processed.add(full)
            
            print(f"Processando Endereço: {full}") # Log para debug
            
            results.append(AddressResult(
                raw_text="...",
                source_pdf="MIND7_AUTO",
                full_address=full,
                associated_names=[],
                is_family_hq=False,
                match_count=1
            ))
        return results
