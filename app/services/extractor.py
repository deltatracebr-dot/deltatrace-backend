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
        
        # Regex melhorado: Exige DDD (XX) ou formato explícito para evitar CPFs
        # Formatos aceitos: (11) 99999-9999, 11 99999 9999, 11999999999
        # O segredo é validar se parece mesmo um telefone
        
        # Captura sequencias de 10 ou 11 digitos
        candidates = re.findall(r'\b\d{10,11}\b', self.text)
        
        # Adiciona também formatos com formatação (xx) xxxx-xxxx
        formatted_candidates = re.findall(r'\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}', self.text)
        
        all_phones = list(set(candidates + formatted_candidates))

        for phone in all_phones:
            # LIMPEZA: Remove caracteres não numéricos para análise
            clean_num = re.sub(r'\D', '', phone)
            
            # FILTRO ANTI-CPF:
            # Se começa com 0, 1, 2, 3, 4, 5, 6, 7, 8 (comuns em CPF) e tem 11 dígitos, 
            # e NÃO tem formatação de telefone perto, é arriscado.
            # Telefones móveis BR começam com DDD + 9.
            
            # Regra simples: Se tem 11 dígitos, o terceiro dígito DEVE ser 9 (Celular)
            if len(clean_num) == 11 and clean_num[2] != '9':
                continue # Provável CPF ou número fixo formatado errado, ignorar
                
            # Regra Anti-Fixo antigo confundido com data:
            if len(clean_num) == 8: continue 

            # Busca contexto no texto original
            escaped_phone = re.escape(phone)
            context_match = re.search(f".{{0,100}}{escaped_phone}.{{0,150}}", self.text, re.DOTALL)
            
            block = context_match.group(0).upper() if context_match else ""
            
            # CLASSIFICAÇÃO
            classification = "Investigar"
            score = 50
            owner = "TERCEIRO / NÃO IDENTIFICADO"

            if self.target_name in block:
                classification = "Pessoal/Confirmado"
                score = 100
                owner = self.target_name
            elif "MÃE" in block or "PAI" in block:
                classification = "Vínculo Familiar"
                score = 70
                owner = "FAMILIAR"
            
            results.append(PhoneResult(
                raw_text=block[:100] + "...", 
                source_pdf="MIND7_AUTO",
                number=phone,
                registered_owner=owner,
                classification=classification,
                confidence_score=score
            ))
            
        return results

    def extract_addresses(self) -> List[AddressResult]:
        results = []
        
        # Regex V2: Mais permissivo. Aceita endereço sem vírgula.
        # Procura: (RUA/AV) + (TEXTO) + (NÚMERO)
        addr_regex = r'((?:RUA|AV|AVENIDA|ALAMEDA|TRAVESSA|RODOVIA|ESTRADA|PRACA)\s+[A-Z\s0-9]+?\s+\d+)'
        
        matches = re.finditer(addr_regex, self.text, re.IGNORECASE)
        processed_addrs = []

        for match in matches:
            full_address = match.group(1).strip().upper()
            
            # Filtra falsos positivos pequenos (ex: "RUA 1")
            if len(full_address) < 8: continue
            
            if full_address in processed_addrs: continue
            processed_addrs.append(full_address)

            # Contexto para buscar nomes
            start = match.start()
            end = match.end()
            block = self.text[max(0, start - 300):min(len(self.text), end + 300)].upper()

            # Extrai nomes possíveis
            blacklist = ["REGISTRO PRINCIPAL", "DATA DE VINCULO", "ENDERECO VINCULADO", "TELEFONE MÓVEL", "BAIRRO:", "CIDADE/UF:", "NÚMERO:", "CEP:"]
            found_names_raw = re.findall(r'\b[A-Z]{3,}\s[A-Z]{3,}\s[A-Z\s]{3,}\b', block)
            
            unique_names = []
            for n in set(found_names_raw):
                n = n.strip()
                if not any(b in n for b in blacklist) and len(n.split()) >= 2:
                    unique_names.append(n)

            # DNA Familiar
            matches_count = 0
            for name in unique_names:
                hits = sum(1 for surname in self.target_surnames if surname in name)
                if hits >= 1: matches_count += 1
            
            is_family_hq = matches_count >= 2
            
            results.append(AddressResult(
                raw_text="...",
                source_pdf="MIND7_AUTO",
                full_address=full_address,
                associated_names=unique_names,
                is_family_hq=is_family_hq,
                match_count=matches_count
            ))

        return results
