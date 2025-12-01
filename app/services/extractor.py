import re
from typing import List
from app.schemas import PhoneResult, AddressResult

class Mind7Extractor:
    def __init__(self, raw_text: str, target_name: str):
        self.text = raw_text
        self.target_name = target_name.upper()
        ignore_words = ["DE", "DA", "DO", "DOS", "DAS", "E", "NETO", "JUNIOR", "FILHO", "SOBRINHO"]
        self.target_surnames = [
            n for n in self.target_name.split() 
            if len(n) > 2 and n not in ignore_words
        ]

    def extract_phones(self) -> List[PhoneResult]:
        results = []
        
        # Regex V3: Telefones + PLACAS (Novo!)
        phone_regex = r'(\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4})'
        placa_regex = r'\b([A-Z]{3}[0-9][0-9A-Z][0-9]{2})\b' # Padrão Mercosul e Antigo

        # 1. Telefones
        found_phones = re.findall(phone_regex, self.text)
        for phone in list(set(found_phones)):
            clean = re.sub(r'\D', '', phone)
            if len(clean) == 11 and clean[2] != '9': continue 
            if len(clean) == 8: continue 

            results.append(PhoneResult(
                raw_text="...", 
                source_pdf="MIND7_AUTO",
                number=phone,
                registered_owner="TERCEIRO",
                classification="Investigar",
                confidence_score=50
            ))

        # 2. Placas (Truque: Salvamos como "PhoneResult" mas com tipo especial no futuro)
        # O backend atual não tem "VehicleResult", então vamos improvisar para não quebrar o sistema agora.
        # No futuro criamos um schema próprio.
        found_placas = re.findall(placa_regex, self.text)
        for placa in list(set(found_placas)):
            results.append(PhoneResult(
                raw_text="VEICULO DETECTADO", 
                source_pdf="MIND7_AUTO",
                number=f"PLACA {placa}", # Prefixo para identificar
                registered_owner="VEICULO",
                classification="Veículo Vinculado",
                confidence_score=90
            ))
            
        return results

    def extract_addresses(self) -> List[AddressResult]:
        results = []
        addr_regex = r'((?:RUA|AV|AVENIDA|ALAMEDA|TRAVESSA|RODOVIA|ESTRADA|PRACA)\s+[A-Z\s0-9]+?\s+\d+)'
        matches = re.finditer(addr_regex, self.text, re.IGNORECASE)
        processed_addrs = []

        for match in matches:
            full_address = match.group(1).strip().upper()
            if len(full_address) < 8 or full_address in processed_addrs: continue
            processed_addrs.append(full_address)

            is_family_hq = any(s in full_address for s in self.target_surnames) # Lógica simplificada
            
            results.append(AddressResult(
                raw_text="...",
                source_pdf="MIND7_AUTO",
                full_address=full_address,
                associated_names=[],
                is_family_hq=is_family_hq,
                match_count=1
            ))

        return results
