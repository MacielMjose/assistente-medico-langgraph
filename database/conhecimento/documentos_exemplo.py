"""Documentos de conhecimento de demonstração para o pipeline RAG.

Cada documento representa uma fonte contextual (protocolo, caso de estudo,
diretriz, referência) que enriquece a resposta da LLM com informações
semanticamente distintas dos registros estruturados do banco relacional.

Todos os documentos abaixo são DADOS DE DEMONSTRAÇÃO — não representam
publicações reais e não devem ser utilizados como base para decisões clínicas.
"""

from langchain_core.documents import Document


def obter_documentos_exemplo() -> list[Document]:
    """Retorna a lista de documentos de conhecimento de exemplo.

    Cada Document possui ``page_content`` com texto contextual e
    ``metadata`` com informações de rastreabilidade da fonte.
    """
    return [
        # ── Protocolos ──────────────────────────────────────────────
        Document(
            page_content=(
                "Protocolo de atendimento para condições respiratórias agudas e crônicas. "
                "Asma brônquica: classificação por gravidade (intermitente, leve persistente, "
                "moderada persistente, grave persistente). Tratamento de primeira linha: "
                "corticosteroide inalatório de baixa dose (budesonida 200-400 mcg/dia ou "
                "beclometasona 200-400 mcg/dia). Broncodilatador de curta ação (salbutamol "
                "100 mcg, 2-4 jatos SOS). Avaliação de controle a cada 1-3 meses. "
                "Critérios de urgência: uso de beta-2 agonista mais de 2 vezes por semana, "
                "despertar noturno por sintomas mais de 2 vezes ao mês, limitação de atividades. "
                "DPOC: classificação GOLD I-IV. Terapia inicial: broncodilatador de longa ação "
                "(anticolinérgico ou beta-2 agonista). Exacerbações: antibioticoterapia + "
                "corticosteroide sistêmico + oxigenoterapia se necessário."
            ),
            metadata={
                "source": "Protocolo Clínico - Condições Respiratórias",
                "document_type": "protocol",
                "title": "Protocolo de Atendimento - Doenças Respiratórias",
                "author": "Departamento de Pneumologia",
                "year": "2024",
                "collection": "protocolos",
            },
        ),
        Document(
            page_content=(
                "Protocolo de atendimento para doenças cardiovasculares. Hipertensão "
                "arterial sistêmica (HAS): classificação por faixas pressóricas. HAS grau 1 "
                "(140-159/90-99 mmHg): mudanças no estilo de vida + monoterapia. HAS grau 2 "
                "(160-179/100-109 mmHg): mudanças no estilo de vida + terapia dupla. "
                "HAS grau 3 (>=180/>=110 mmHg): terapia tripla. Primeira linha: IECA "
                "(enalapril 10-20mg/dia, losartana 50-100mg/dia) ou BRA, ou CCB "
                "(anlodipino 5-10mg/dia), ou diurético tiazídico (clortalidona 12.5-25mg/dia). "
                "Insuficiência cardíaca com fração de ejeção reduzida: IECA/BRA + betabloqueador "
                "(carvedilol, bisoprolol ou metoprolol succinato) + diurético de alça + "
                "aldosterona antagonist quando indicado. Monitorar função renal e potássio."
            ),
            metadata={
                "source": "Protocolo Clínico - Doenças Cardiovasculares",
                "document_type": "protocol",
                "title": "Protocolo de Atendimento - Cardiovasculares",
                "author": "Departamento de Cardiologia",
                "year": "2024",
                "collection": "protocolos",
            },
        ),
        Document(
            page_content=(
                "Protocolo de emergência para reações alérgicas graves. Anafilaxia: "
                "definição - reação alérgica sistêmica aguda com comprometimento de "
                "mais de um sistema orgânico. Apresentação clássica: urticária + "
                "broncoespasmo + hipotensão. Tratamento imediato: adrenalina "
                "1:1000 (0,3-0,5 mg IM na face anterolateral da coxa), repetir a cada "
                "5-15 minutos se necessário. Posicionamento: decúbito dorsal com elevação "
                "dos membros inferiores (exceto se dispneia - sentar). Oxigênio suplementar "
                "mascara 15L/min. Hidratação venosa: SF 0,9% 500mL em bolus para adultos. "
                "Antihistamínico H1 (difenidramina 25-50mg IV) como coadjuvante. "
                "Corticosteroide (hidrocortisona 200mg IV ou metilprednisolona 125mg IV) "
                "para prevenir segunda onda. Observação mínima de 4-6 horas. "
                "Todos os pacientes devem receber prescrição de auto-injetor de adrenalina "
                "para uso domiciliar e encaminhamento a alergista."
            ),
            metadata={
                "source": "Protocolo de Emergência - Reações Alérgicas",
                "document_type": "protocol",
                "title": "Protocolo de Emergência - Anafilaxia e Reações Alérgicas",
                "author": "Departamento de Emergência",
                "year": "2024",
                "collection": "protocolos",
            },
        ),
        # ── Casos de estudo ────────────────────────────────────────
        Document(
            page_content=(
                "Caso clínico: paciente feminina, 52 anos, com diagnóstico de diabetes "
                "mellitus tipo 2 há 8 anos, obesidade grau II (IMC 37,2 kg/m²), "
                "hipertensão arterial sistêmica em uso de losartana 50mg/dia e "
                "amlodipino 5mg/dia. Apresenta hemoglobina glicada de 9,2% e "
                "microalbuminúria. Quadro clínico compatível com síndrome metabólica "
                "com critérios de resistência insulínica. Conduta: intensificação do "
                "tratamento hipoglicemiante com metformina 850mg 2x/dia + empagliflozina "
                "25mg/dia (benefício cardiovascular comprovado). Orientação alimentar "
                "por nutricionista. Programa de atividade física supervisada. "
                "Controle rigoroso da PA meta <130/80 mmHg. Reavaliação em 3 meses "
                "com HbA1c, perfil lipídico, função renal e fundoscopia."
            ),
            metadata={
                "source": "Casos de Estudo - Transtornos Metabólicos",
                "document_type": "case_study",
                "title": "Síndrome Metabólica com Complicações Microvasculares",
                "author": "Equipe Clínica - Casos Demonstrativos",
                "year": "2024",
                "collection": "casos_de_estudo",
            },
        ),
        Document(
            page_content=(
                "Caso clínico: paciente masculino, 67 anos, com queixa de cefaleia "
                "crônica diária há 3 meses, resistente a analgésicos convencionais. "
                "Histórico de enxaqueca sem aura desde os 20 anos, com piora progressiva. "
                "Uso frequente de analgésicos: dipirona 1g 3x/dia + ibuprofeno 600mg 2x/dia "
                "há 2 meses. Critérios para cefaleia por uso excessivo de medicação (HOT): "
                "dias de cefaleia >= 15/mês + uso de analgésicos >= 10-15 dias/mês. "
                "Conduta: descontinuação gradual dos analgésicos (tapering em 2 semanas). "
                "Profilaxia: amitriptilina 25mg ao dia (iniciar 10mg, titulação gradual). "
                "Programa de reabilitação: fisioterapia cranio-cervical, técnicas de "
                "relaxamento, higiene do sono. Monitoramento semanal nas primeiras 4 semanas. "
                "Avaliação neurológica complementar: ressonância magnética de crânio."
            ),
            metadata={
                "source": "Casos de Estudo - Condições Neurológicas",
                "document_type": "case_study",
                "title": "Cefaleia Crônica por Uso Excessivo de Analgésicos",
                "author": "Equipe Neurológica - Casos Demonstrativos",
                "year": "2024",
                "collection": "casos_de_estudo",
            },
        ),
        # ── Diretrizes ─────────────────────────────────────────────
        Document(
            page_content=(
                "Diretrizes de prescrição e interações medicamentosas. Polifarmácia: "
                "definição - uso concomitante de 5 ou mais medicamentos. Riscos principais: "
                "interações medicamentosas, não adesão, efeitos adversos cumulativos. "
                "Interações clinicamente relevantes: IECA + suplementos de potássio → "
                "hipercalemia; AAS + varfarina → risco hemorrágico; IECA + BRA → "
                "não associar (risco de hipercalemia e insuficiência renal); "
                "estatinas + macrólidos → miopatia; metformina + contraste iodado → "
                "pausar 48h antes e depois. Avaliação de Beers: lista de medicamentos "
                "potencialmente inapropriados para idosos (benzodiazepínicos, AINEs "
                "prolongados, anticolinérgicos, antiarrítmicos classe Ia). "
                "Revisão medicamentosa: realizar a cada 6 meses em pacientes polimedicados. "
                "Estratégias de desprescrição: critérios STOPP/START, terapia escalonada."
            ),
            metadata={
                "source": "Diretrizes de Prescrição - Interações Medicamentosas",
                "document_type": "guideline",
                "title": "Diretrizes para Uso Seguro de Medicamentos",
                "author": "Comitê de Farmacologia Clínica",
                "year": "2024",
                "collection": "diretrizes",
            },
        ),
        Document(
            page_content=(
                "Diretrizes de exames complementares e suas indicações. Hemograma "
                "completo: indicado em triagem, investigação de anemia, infecções, "
                "hemoglobinopatias. Valores de referência: hemoglobina 12-16 g/dL "
                "(mulheres), 14-18 g/dL (homens); leucócitos 4.000-11.000/mm³; "
                "plaquetas 150.000-450.000/mm³. Perfil lipídico: colesterol total, "
                "LDL, HDL, triglicerídeos. Jejum de 12h. Meta LDL <100 mg/dL (baixo risco), "
                "<70 mg/dL (alto risco), <55 mg/dL (muito alto risco). "
                "Glicemia de jejum: normal <100 mg/dL, pré-diabetes 100-125 mg/dL, "
                "diabetes >= 126 mg/dL. HbA1c: normal <5,7%, pré-diabetes 5,7-6,4%, "
                "diabetes >= 6,5%. TSH: screening de disfunção tireoidiana, normal 0,4-4,0 "
                "mUI/L. Função renal: creatinina + TFG estimada (CKD-EPI). "
                "Exame de urina: proteinúria, hematuria, leucocituria, cilindros."
            ),
            metadata={
                "source": "Diretrizes de Exames Complementares",
                "document_type": "guideline",
                "title": "Guia de Interpretação de Exames Laboratoriais",
                "author": "Departamento de Patologia Clínica",
                "year": "2024",
                "collection": "diretrizes",
            },
        ),
        # ── Referências bibliográficas ─────────────────────────────
        Document(
            page_content=(
                "Referência bibliográfica sobre dor crônica: classificação e abordagem. "
                "Classificação da dor (IASP): nociceptiva (somática, visceral), "
                "neuropática (periférica, central), nociplástica. Escala visual numérica "
                "(EVN): 0-10, onde 0 = sem dor e 10 = pior dor possível. "
                "Escala de faces de Wong-Baker: útil para crianças e idosos. "
                "Abordagem multimodal: farmacológica (paracetamol 750mg 6/6h, AINEs, "
                "opioides fracos para dor moderada, opioides fortes para dor grave), "
                "não-farmacológica (fisioterapia, psicoterapia cognitivo-comportamental, "
                "acupuntura, TENS). Escalera analgésica da OMS adaptada: nível 1 - "
                "dor leve (paracetamol/AINE), nível 2 - dor moderada (triamadol/codeína), "
                "nível 3 - dor grave (morfina, oxicodona). Avaliação do risco de dependência "
                "antes de prescrever opioides. Reavaliação periódica da eficácia e efeitos "
                "adversos. Encaminhamento para centro de dor quando dor persistente > 3 meses."
            ),
            metadata={
                "source": "Referência Bibliográfica - Dor Crônica",
                "document_type": "reference",
                "title": "Classificação e Manejo da Dor Crônica",
                "author": "Associação Brasileira para o Estudo da Dor",
                "year": "2023",
                "collection": "referencias",
            },
        ),
    ]
