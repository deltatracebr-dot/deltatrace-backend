import re
from typing import List
from app.schemas import PhoneResult, AddressResult

class Mind7Extractor:
    def __init__(self, raw_text: str, target_name: str):
        self.text = raw_text
        self.target_name = target_name.upper()
        # Quebra o nome do alvo para análise de sobrenome (ex: VINICIUS RODRIGUES DE ASSIS)
        # Ignora preposições como DE, DA, DOS, E
        ignore_words = ["DE", "DA", "DO", "DOS", "DAS", "E", "NETO", "JUNIOR", "FILHO", "SOBRINHO"]
        self.target_surnames = [
            n for n in self.target_name.split() 
            if len(n) > 2 and n not in ignore_words
        ]

    def extract_phones(self) -> List[PhoneResult]:
        """
        Lógica: Busca blocos de telefone e decide se é Próprio ou Terceiro.
        """
        results = []
        # Tenta dividir o texto em linhas para processar melhor
        lines = self.text.split('\n')
        
        # Regex para capturar telefones (formato (XX) 9XXXX-XXXX ou similar)
        phone_regex = r'(\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4})'

        # Simulação de análise de blocos (Ajustar conforme layout real do PDF)
        # Aqui vamos varrer o texto procurando padrões de vínculo
        
        # Pega todos os matches de telefone no texto inteiro
        found_phones = re.findall(phone_regex, self.text)
        unique_phones = list(set(found_phones))

        for phone in unique_phones:
            # Pega o contexto ao redor do telefone (100 caracteres antes e depois)
            escaped_phone = re.escape(phone)
            context_match = re.search(f".{{0,100}}{escaped_phone}.{{0,200}}", self.text, re.DOTALL)
            
            if not context_match:
                continue
                
            block = context_match.group(0).upper()
            
            # ANÁLISE DE INTELIGÊNCIA (Regra de Negócio)
            classification = "Investigar"
            score = 50
            owner = "NÃO IDENTIFICADO"

            # Tenta achar o titular no bloco
            # Procura por padrões comuns de relatório como "NOME: FULANO" ou apenas nomes maiúsculos perto
            # Esta é uma heurística simples
            
            if self.target_name in block:
                classification = "Pessoal/Confirmado"
                score = 100
                owner = self.target_name
            else:
                # Se o nome do alvo não está perto, deve ser de terceiro
                classification = "Vínculo com Terceiro/Laranja"
                score = 60 # Ainda relevante pois estava no dossiê
                # Tenta extrair um nome próximo (muito básico, melhoraria com layout fixo)
                owner = "TERCEIRO (Verificar PDF)"

            results.append(PhoneResult(
                raw_text=block[:100] + "...", 
                source_pdf="UPLOAD_MIND7",
                number=phone,
                registered_owner=owner,
                classification=classification,
                confidence_score=score
            ))
            
        return results

    def extract_addresses(self) -> List[AddressResult]:
        """
        Lógica: Busca endereços e conta sobrenomes para achar o QG.
        """
        results = []
        
        # Regex genérico para endereços (RUA, AV, ALAMEDA...)
        addr_regex = r'(RUA|AV|AVENIDA|ALAMEDA|TRAVESSA|RODOVIA)\s+[^,]+,\s*\d+'
        found_addresses = re.findall(addr_regex, self.text, re.IGNORECASE)
        
        # Precisamos pegar o endereço completo, o findall acima pega só o tipo.
        # Vamos usar um iterador para pegar o match completo
        matches = re.finditer(r'((?:RUA|AV|AVENIDA|ALAMEDA|TRAVESSA|RODOVIA)\s+[^,\n]+,\s*\d+[^,\n]*)', self.text, re.IGNORECASE)

        processed_addrs = []

        for match in matches:
            full_address = match.group(1).strip().upper()
            if full_address in processed_addrs: continue
            processed_addrs.append(full_address)

            # Pega contexto para buscar nomes
            start = match.start()
            end = match.end()
            # Olha 300 caracteres antes e depois para achar nomes vinculados
            context_start = max(0, start - 300)
            context_end = min(len(self.text), end + 300)
            block = self.text[context_start:context_end].upper()

            # Extrai nomes no bloco (Padrão: 3 palavras maiúsculas)
            found_names_raw = re.findall(r'\b[A-Z]{3,}\s[A-Z]{3,}\s[A-Z]{3,}\b', block)
            
            # Filtra nomes irrelevantes (cabeçalhos do PDF)
            blacklist = ["REGISTRO PRINCIPAL", "DATA DE VINCULO", "ENDERECO VINCULADO", "TELEFONE MÓVEL"]
            unique_names = []
            for n in set(found_names_raw):
                if not any(b in n for b in blacklist):
                    unique_names.append(n)

            # ALGORITMO DE DNA FAMILIAR
            matches_count = 0
            for name in unique_names:
                # Se o nome tem sobrenomes do alvo (ex: RODRIGUES ou ASSIS)
                hits = sum(1 for surname in self.target_surnames if surname in name)
                if hits >= 1: # Pelo menos 1 sobrenome igual
                    matches_count += 1
            
            # Se tiver nomes com mesmo sobrenome e não for o próprio alvo
            is_family_hq = matches_count >= 2
            
            if is_family_hq:
                full_address += " [📍 POSSÍVEL QG FAMILIAR]"

            results.append(AddressResult(
                raw_text="...",
                source_pdf="UPLOAD_MIND7",
                full_address=full_address,
                associated_names=unique_names,
                is_family_hq=is_family_hq,
                match_count=matches_count
            ))

        return results
