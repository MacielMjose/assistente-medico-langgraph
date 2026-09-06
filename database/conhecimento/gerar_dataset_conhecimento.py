"""Gera um corpus documental sintético de alta fidelidade (mock de "um real").

Complementa o corpus real (PCDTs/manuais oficiais baixados por
``baixar_fontes_reais.py``) com conteúdo didático por especialidade, cobrindo
áreas que não possuem PCDT oficial no corpus (dermatologia, psiquiatria,
obstetrícia, pediatria, etc.).

Cada especialidade gera 3 PDFs multi-página (manual de condutas, guia de
prescrição e protocolo de atendimento) e 1 planilha de posologia. O conteúdo é
plausível e usa doses/condutas reconhecidas, porém é MARCADO como sintético e
NÃO deve ser usado como base para decisões clínicas.

Os arquivos gerados são registrados em ``knowledge/metadados_fontes.json`` com
``sintetico: true`` para permitir rastreabilidade e filtragem.

Uso:
    python database/conhecimento/gerar_dataset_conhecimento.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

KNOWLEDGE = RAIZ / "knowledge"
PDF_DIR = KNOWLEDGE / "pdf"
EXCEL_DIR = KNOWLEDGE / "excel"
METADADOS = KNOWLEDGE / "metadados_fontes.json"

AUTOR_DIDATICO = "Equipe Didática (Assistente Médico)"
LICENCA_SINTETICA = (
    "Material didático sintético de demonstração. Conteúdo plausível, porém "
    "não oficial; não deve ser usado como base para decisões clínicas."
)

# Cada especialidade: medicamentos, CIDs, exames, sinais de alarme e condutas.
ESPECIALIDADES: dict[str, dict] = {
    "cardiologia": {
        "nome": "Cardiologia",
        "medicamentos": [
            {"nome": "Enalapril", "classe": "IECA", "dose": "10-20 mg 2x/dia VO", "indicacao": "IC com fração de ejeção reduzida e HAS", "advertencia": "Monitorar potássio e creatinina; contraindicado na gestação (teratogênico)"},
            {"nome": "Carvedilol", "classe": "Betabloqueador", "dose": "3,125-25 mg 2x/dia VO com titulação", "indicacao": "IC estável classe II-IV", "advertencia": "Contraindicado em bradicardia sintomática e choque cardiogênico"},
            {"nome": "Furosemida", "classe": "Diurético de alça", "dose": "20-80 mg/dia VO; IV 20-40 mg em congestão aguda", "indicacao": "Congestão pulmonar e edema periférico na IC", "advertencia": "Vigiar hipocalemia, hiponatremia e disfunção renal"},
            {"nome": "Espironolactona", "classe": "Antialdosterônico", "dose": "25-50 mg/dia VO", "indicacao": "IC NYHA II-IV e pós-IAM com disfunção", "advertencia": "Risco de hipercalemia; contraindicado se K > 5,0 mEq/L"},
            {"nome": "Amiodarona", "classe": "Antiarrítmico classe III", "dose": "Carga 800-1600 mg/dia por 1-3 semanas, manutenção 200 mg/dia", "indicacao": "Fibrilação atrial e taquiarritmias ventriculares", "advertencia": "Risco de tireoidopatia, fotossensibilidade e lesão pulmonar; controlar função tireoidiana"},
            {"nome": "Apixabana", "classe": "Anticoagulante oral direto", "dose": "5 mg 2x/dia VO (2,5 mg se critérios)", "indicacao": "Prevenção de AVC na fibrilação atrial não valvar", "advertencia": "Ajustar dose em disfunção renal e idade avançada"},
        ],
        "cids": [
            ("I50", "Insuficiência cardíaca"), ("I48", "Fibrilação atrial"),
            ("I20", "Angina instável"), ("I21", "Infarto agudo do miocárdio"),
            ("R07.2", "Dor torácica"), ("I46", "Parada cardiorrespiratória"),
        ],
        "exames": [
            ("Ecocardiograma transtorácico", "Avaliar fração de ejeção e função valvar na suspeita de IC"),
            ("Eletrocardiograma de 12 derivações", "Rastrear isquemia, arritmias e bloqueios em dor torácica"),
            ("Troponina ultrassensível", "Diagnóstico de síndrome coronariana aguda (0h-1h/3h)"),
            ("Peptídeo natriurético tipo B (BNP)", "Marcador de congestão na IC (BNP > 100 pg/mL sugere IC)"),
            ("Hemograma, creatinina, eletrólitos e TSH", "Avaliação complementar e causas precipitantes"),
        ],
        "sinais_alarme": [
            "Dor torácica em aperto com irradiação para mandíbula ou braço esquerdo",
            "Dispneia súbita associada a dor torácica ou hemoptise (suspeita de TEP)",
            "Síncope de esforço ou com palpação de pulso irregular",
            "Hipotensão (PAS < 90 mmHg) com sinais de congestão",
            "IC de novo refratária ao tratamento inicial",
        ],
        "condutas": [
            ("Dor torácica com supradesnivelamento de ST", "Acionar protocolo de IAM com ST; reperfusão nas primeiras 2 horas"),
            ("IC descompensada com congestão grave", "Internação; diurético IV, restrição hídrica e monitorização de peso"),
            ("Abd piora funcional NYHA com FE reduzida", "Todos: IECA/BRA + betabloqueador + espironolactona"),
            ("Fibrilação atrial de início recente", "Anticoagulação (CHA2DS2-VASc), controle de frequência ou ritmo"),
            ("Pós-alta de IC", "Reavaliação em 7-14 dias; educação sobre peso diário e sintomas congestivos"),
        ],
    },
    "dermatologia": {
        "nome": "Dermatologia",
        "medicamentos": [
            {"nome": "Hidrocortisona 1% pomada", "classe": "Corticosteroide tópico", "dose": "Aplicar 1-2x/dia em área afetada", "indicacao": "Dermatite atópica leve e eczema", "advertencia": "Evitar uso prolongado no rosto e regiões de dobra"},
            {"nome": "Desloratadina", "classe": "Anti-histamínico H1 não sedativo", "dose": "5 mg/dia VO", "indicacao": "Prurido e urticária alérgica", "advertencia": "Sem interação relevante; seguro na gestação com orientação"},
            {"nome": "Metotrexato", "classe": "Imunossupressor", "dose": "15 mg 1x/semana VO/IM com ácido fólico 5 mg/semana", "indicacao": "Psoríase moderada a grave", "advertencia": "Controlar hemograma e função hepática; teratogênico; risco de fibrose pulmonar"},
            {"nome": "Calcipotriol 0,005% pomada", "classe": "Análogo de vitamina D", "dose": "Aplicar 2x/dia", "indicacao": "Placas psoriásicas", "advertencia": "Não associar em mesma área a alto teor de corticosteroide"},
            {"nome": "Cefalexina", "classe": "Cefalosporina de 1ª geração", "dose": "500 mg 4x/dia VO por 7-10 dias", "indicacao": "Celulite e erisipela leves", "advertencia": "Ajustar em disfunção renal; hipersensibilidade a beta-lactâmico"},
            {"nome": "Desonida 0,05% creme", "classe": "Corticosteroide tópico de baixa potência", "dose": "1-2x/dia por até 3 semanas", "indicacao": "Dermatite atópica facial em crianças", "advertencia": "Evitar oclusão e uso prolongado"},
        ],
        "cids": [
            ("L20", "Dermatite atópica"), ("L40", "Psoríase"), ("L03", "Celulite"),
            ("L50", "Urticária"), ("B35", "Dermatofitose (tinha)"), ("L02", "Abscesso cutâneo"),
        ],
        "exames": [
            ("Cultura de punção-biópsia de pele", "Diagnóstico etiológico de celulite com sinais sistêmicos"),
            ("Biópsia de pele (punch 4 mm)", "Confirmação histológica de psoríase e dermatoses"),
            ("Teste de contato (patch test)", "Investigar dermatite de contato alérgica"),
            ("Exame micológico direto com KOH", "Confirmar dermatofitose"),
            ("Hemograma e PCR", "Apoio diagnóstico em infecções de pele extensas"),
        ],
        "sinais_alarme": [
            "Celulite com bolhas hemorrágicas, equimose ou necrose (suspeita de fascite necrosante)",
            "Eritema extenso e doloroso de rápida progressão com dor desproporcional",
            "Impetigo/erisipela em paciente imunossuprimido ou diabético descompensado",
            "Sinais sistêmicos (febre, hipotensão, taquicardia) associados a infecção cutânea",
            "Fácias incluir necrose central ou pústulas confluentes com febre (pensar em pioderma gangrenoso)",
        ],
        "condutas": [
            ("Celulite leve sem sinais sistêmicos", "Cefalexina VO ambulatorial com retorno em 48h se piora"),
            ("Suspeita de fascite necrosante", "Emergência cirúrgica: antibiótico IV de amplo espectro + necrosectomia"),
            ("Psoríase extensa descontrolada", "Encaminhar a dermatologia; avaliar metotrexato ou fototerapia"),
            ("Eczema atópico com infecção secundária", "Corticosteroide tópico + antisséptico; higiene e emoliente"),
            ("Prurido intenso sem lesão", "Investigar causas sistêmicas (colestase, DRC, tireoide) antes de tratar"),
        ],
    },
    "endocrinologia": {
        "nome": "Endocrinologia",
        "medicamentos": [
            {"nome": "Levotiroxina", "classe": "Hormônio tireoidiano", "dose": "1,6 mcg/kg/dia VO em jejum; iniciar 50 mcg/dia em adultos", "indicacao": "Hipotireoidismo primário", "advertencia": "Reavaliar TSH em 6-8 semanas após ajuste; evitar com ferro e cálcio"},
            {"nome": "Metimazol", "classe": "Antitireoidiano", "dose": "10-30 mg/dia VO", "indicacao": "Hipertireoidismo (Doença de Graves)", "advertencia": "Risco de agranulocitose; suspender se febre ou faringite"},
            {"nome": "Colecalciferol (Vitamina D3)", "classe": "Vitamina", "dose": "1000-2000 UI/dia ou 50.000 UI/semana por 8 semanas em deficiência", "indicacao": "Hipovitaminose D e risco de osteoporose", "advertencia": "Vigiar cálcio; evitar doses suprafisiológicas prolongadas"},
            {"nome": "Hidrocortisona", "classe": "Glicocorticoide", "dose": "Manutenção 15-25 mg/dia em 2-3 tomadas (crise: 100 mg IV em bolus)", "indicacao": "Insuficiência adrenal e crise adrenal", "advertencia": "Dobrar dose em estresse; paciente deve ter identificação de risco"},
            {"nome": "Cabergolina", "classe": "Agonista dopaminérgico", "dose": "0,25-0,5 mg 2x/semana VO", "indicacao": "Prolactinoma e hiperprolactinemia", "advertencia": "Monitorar função cardíaca em uso crônico de doses altas"},
        ],
        "cids": [
            ("E03", "Hipotireoidismo"), ("E05", "Tireotoxicose"), ("E27", "Insuficiência adrenal"),
            ("E22.8", "Hiperprolactinemia"), ("E55", "Deficiência de vitamina D"), ("E04", "Bócio não tóxico"),
        ],
        "exames": [
            ("TSH e T4 livre", "Rastreio e monitoramento de tireoidopatias"),
            ("Hemograma com plaquetas", "Monitorar nas drogas antitireoidianas"),
            ("Cortisol basal e teste de ACTH", "Avaliação da função adrenal"),
            ("Densitometria óssea", "Estratificação de risco de fratura em hipogonadismo"),
            ("Prolactina sérica", "Investigação de galactorreia e disfunção gonadal"),
        ],
        "sinais_alarme": [
            "Febre, vômitos e hipotensão em usuário de glicocorticoide (crise adrenal)",
            "TSH < 0,01 com sintomas adrenérgicos e perda de peso (tempestade tireoidiana)",
            "Hipercalcemia grave com confusão e poliúria",
            "Cefaleia com alteração campimétrica em paciente com adenoma",
            "Hiponatremia com hiposmolalidade em suspeita de hipoadrenalismo",
        ],
        "condutas": [
            ("Crise tireotóxica", "Emergência: tionamida + betabloqueador + glicocorticoide + suporte em UTI"),
            ("Hipotireoidismo leve (TSH 4-10)", "Repetir painel; tratar se sintomas ou anticorpos positivos"),
            ("Profilaxia tireoidiana pré-operação", "Metimazol até eutireoideu ou dose baixa + sobrecarga de iodo"),
            ("Deficiência de vitamina D assintomática", "Reposição com doses de manutenção e reavaliação óssea"),
            ("Gestante com hipotireoidismo", "Ajuste da levotiroxina (aumento de 30-50% usual) com TS  trimestral"),
        ],
    },
    "gastroenterologia": {
        "nome": "Gastroenterologia",
        "medicamentos": [
            {"nome": "Omeprazol", "classe": "IBP", "dose": "20-40 mg 1x/dia VO em jejum", "indicacao": "DRGE, úlcera péptica e proteção gástrica", "advertencia": "Uso prolongado: monitorar deficiência de B12 e magnésio"},
            {"nome": "Domperidona", "classe": "Procinético", "dose": "10 mg 3x/dia antes das refeições", "indicacao": "Gastroparesia e dispepsia", "advertencia": "Risco de prolongamento do QT/interações; cautela em cardiopatas"},
            {"nome": "Metoclopramida", "classe": "Procinético antidopaminérgico", "dose": "10 mg até 3x/dia VO/IV", "indicacao": "Náuseas e vômitos e gastroparesia", "advertencia": "Máximo 5 dias de uso para evitar discinesia tardia"},
            {"nome": "Mebeverina", "classe": "Antiespasmódico", "dose": "200 mg 2x/dia VO", "indicacao": "Dor abdominal funcional e síndrome do intestino irritável", "advertencia": "Contraindicada em doenças inflamatórias intestinais ativas"},
            {"nome": "Esquema triplo p/ H. pylori", "classe": "Terapia de erradicação", "dose": "IBP 2x + amoxicilina 1g 2x + claritromicina 500 mg 2x por 14 dias", "indicacao": "Erradicação de Helicobacter pylori", "advertencia": "Confirmação pós-tratamento com teste respiratório"},
            {"nome": "Tioridazina 25 mg", "classe": "Antiespasmódico (não usado)", "dose": "—", "indicacao": "—", "advertencia": "Não recomendado; evitar em gastroenteropatias"},
        ],
        "cids": [
            ("K21", "Doença do refluxo gastroesofágico"), ("K25", "Úlcera gástrica"),
            ("K26", "Úlcera duodenal"), ("K59", "Distúrbios funcionais intestinais"),
            ("K58", "Síndrome do intestino irritável"), ("A09", "Gastroenterite diarreica"),
        ],
        "exames": [
            ("Endoscopia digestiva alta", "DRGE refratária, disfagia, anemia e sangramento"),
            ("Teste respiratório da ureia", "Diagnóstico e controle de H. pylori"),
            ("Ultrassonografia de abdome total", "Cólica biliar e avaliação de vias biliares"),
            ("Calprotectina fecal", "Triagem de doença inflamatória intestinal"),
            ("Colonoscopia", "Rastreio (50 anos) e sangramento/alteração do hábito"),
        ],
        "sinais_alarme": [
            "Disfagia progressiva ou odinofagia",
            "Perda de peso não intencional (> 5% em 6 meses)",
            "Anemia ferropriva ou melena/sangramento digestivo",
            "Vômitos persistentes ou hematêmese",
            "Massa abdominal palpável ou linfadenopatia supraclavicular",
            "Sangramento retal após 40 anos com mudança do hábito intestinal",
        ],
        "condutas": [
            ("DRGE clássica sem alarme", "Teste de IBP 8 semanas + medidas posturais; endoscopia se recidiva"),
            ("Hematêmese com choque", "Estabilizar vias aéreas, acessos, transfusão e endoscopia precoce"),
            ("Diarreia aguda com desidratação", "Hidratação oral/EV; evitar antidiarreico se febre ou sangue"),
            ("Anemia ferropriva na mulher", "Investigar ginecológico e endoscópico; reposição de ferro"),
            ("Disfagia com alarme", "Endoscopia em até 2 semanas; excluir neoplasia esofágica"),
        ],
    },
    "geriatria": {
        "nome": "Geriatria",
        "medicamentos": [
            {"nome": "Quetiapina", "classe": "Antipsicótico atípico", "dose": "12,5-50 mg à noite em delirium; 25-100 mg/dia em psicose do idoso", "indicacao": "Delirium hiperativo e sintomas comportamentais", "advertencia": "Risco de AVC e mortalidade em pacientes com demência; usar a menor dose e tempo"},
            {"nome": "Donepezila", "classe": "Inibidor da acetilcolinesterase", "dose": "5 mg/dia VO, titular para 10 mg", "indicacao": "Doença de Alzheimer leve a moderada", "advertencia": "Monitorar bradicardia; cuidado com anti-inflamatórios e úlcera"},
            {"nome": "Ácido fólico", "classe": "Vitamina", "dose": "1 mg/dia VO", "indicacao": "Anemia megaloblástica e correção nutricional", "advertencia": "Antes de repor, descartar deficiência de B12 pura (risco de mascar neuropatia)"},
            {"nome": "Vitamina B12 (hidroxicobalamina)", "classe": "Vitamina", "dose": "1000 mcg/dia IM por 1 semana, depois semanal por 4 semanas, mensal manutenção", "indicacao": "Deficiência de B12 e anemia perniciosa", "advertencia": "Monitorar potássio durante o início do tratamento"},
            {"nome": "Paracetamol", "classe": "Analgésico", "dose": "500-1000 mg até 4x/dia (máx. 3 g/dia no idoso)", "indicacao": "Dor osteoarticular e cefaleia", "advertencia": "Vigiar função hepática; evitar dose máx. em hepatopatas"},
        ],
        "cids": [
            ("F05", "Delirium"), ("G30", "Doença de Alzheimer"), ("R29.6", "Risco de queda"),
            ("D51", "Anemia por deficiência de B12"), ("F03", "Demência não especificada"), ("S72.0", "Fratura de colo de fêmur"),
        ],
        "exames": [
            ("Mini-exame do estado mental (MEEM)", "Triagem cognitiva e seguimento de demências"),
            ("Escala de Katz (AVD) e Lawton (AIVD)", "Avaliação funcional do idoso"),
            ("Teste do relógio", "Rastreio rápido de disfunção executiva"),
            ("Densitometria óssea", "Osteoporose e risco de fratura"),
            ("Vitamina B12, TSH e eletrólitos", "Causas reversíveis de confusão e fraqueza"),
        ],
        "sinais_alarme": [
            "Início agudo de confusão com flutuação (delirium) — buscar causa orgânica",
            "Queda com trauma craniano em anticoagulante (TC de crânio) e queda recorrente",
            "Síncope ou tontura ao levantar (hipotensão ortostática ou arritmia)",
            "Febre em idoso frágil com Taquicardia — investigar infecção de forma ampla",
            "Desidratação e hiponatremia com polifarmácia",
        ],
        "condutas": [
            ("Delirium agudizado", "Tratar causa base + ambiente (luz, orientação) + baixa dose antipsicótico se risco"),
            ("Queda por polifarmácia", "Revisão de medicações (critérios STOPP/START); retirar drogas desnecessárias"),
            ("Fratura de fêmur", "Cirurgia em até 48h quando estável; analgesia e tromboprofilaxia"),
            ("Hipotensão ortostática sintomática", "Suspender hipotensores potenciais e orientar mudanças de posição lentas"),
            ("Demência com comportamentos", "Abordagem não farmacológica 1ª linha; medicação última, menor dose"),
        ],
    },
    "infectologia": {
        "nome": "Infectologia",
        "medicamentos": [
            {"nome": "Nitrofurantoína", "classe": "Antibiótico urinário", "dose": "100 mg 2x/dia VO por 5 dias", "indicacao": "Cistite não complicada", "advertencia": "Contraindicada em insuficiência renal (CICr < 60); não usar na pielonefrite"},
            {"nome": "Fosfomicina trometamol", "classe": "Antibiótico urinário", "dose": "3 g dose única VO", "indicacao": "Cistite não complicada (alternativa)", "advertencia": "Tomar em jejum à noite"},
            {"nome": "Amoxicilina-clavulanato", "classe": "Aminopenicilina", "dose": "875/125 mg 2x/dia VO", "indicacao": "Pneumonia comunitária em comorbidades e sinusite bacteriana", "advertencia": "Risco de hepatotoxicidade (especialmente em idosos)"},
            {"nome": "Ceftriaxona", "classe": "Cefalosporina 3ª geração", "dose": "1-2 g/dia IV/IM", "indicacao": "Pneumonia e pielonefrite hospitalizadas", "advertencia": "Evitar em recém-nascidos com hiperbilirrubinemia; risco de biliar em idosos"},
            {"nome": "Azitromicina", "classe": "Macrolídeo", "dose": "500 mg 1x/dia por 5 dias", "indicacao": "Pneumonia atípica e coqueluche", "advertencia": "Risco de prolongamento QT; reações adversas gastrointestinais"},
            {"nome": "Clindamicina", "classe": "Lincosamida", "dose": "300-600 mg 4x/dia VO/IV", "indicacao": "Infecções anaeróbias e de pele/partes moles", "advertencia": "Risco de colite associada a Clostridioides difficile"},
        ],
        "cids": [
            ("N39.0", "Infecção do trato urinário"), ("J15.9", "Pneumonia bacteriana"),
            ("A46", "Erisipela"), ("A08", "Gastroenterite viral"), ("J18.9", "Pneumonia não especificada"),
            ("A41", "Sepse"),
        ],
        "exames": [
            ("Urina I e urocultura", "Confirmação de ITU e teste de sensibilidade"),
            ("Hemograma, PCR e procalcitonina", "Apoio diagnósticator no contexto respiratório e séptico"),
            ("Hemoculturas (2 amostras)", "Antes do antibiótico na suspeita de sepse"),
            ("Radiografia de tórax", "Pneumonia comunitária e seguimento"),
            ("Teste rápido de antígeno urinário (legionella/pneumococo)", "Casos selecionados de pneumonia grave"),
        ],
        "sinais_alarme": [
            "Sepse: febre/hipotermia + taquicardia + PAS < 90 ou lactato elevado",
            "Pneumonia com hipoxemia, confusão ou comorbidades descompensadas",
            "Meningite: cefaleia intensa + rigidez de nuca + vômitos e febre",
            "Celulite com bolhas e dor desproporcional (fascite necrosante)",
            "ITU febril em gestante ou imunossuprimido",
        ],
        "condutas": [
            ("Sepse na emergência", "Culturas + antibiótico de largo espectro na primeira hora + cristaloide 30 ml/kg"),
            ("Pneumonia comunitária leve", "Amoxicilina/amoxicilina-clavulanato ambulatorial com retorno em 72h"),
            ("Cistite em gestante", "Tratar sempre (risco de prematuridade); evitar nitrofurantoína no 3º trimestre"),
            ("Fascite necrosante", "Cirurgia imediata + clindamicina + beta-lactâmico + suporte"),
            ("Meningite comunitária", "Antibiótico empírico (ceftriaxona) e dexametasona antes se pneumococo"),
        ],
    },
    "nefrologia": {
        "nome": "Nefrologia",
        "medicamentos": [
            {"nome": "Enalapril/IECA ou losartana", "classe": "RAS", "dose": "Renoproteção com titulação até dose máxima tolerada", "indicacao": "Proteinúria e DRC (estágios 1-4)", "advertencia": "Monitorar potássio e creatinina 1-2 semanas após início"},
            {"nome": "Furosemida", "classe": "Diurético de alça", "dose": "20-80 mg/dia VO ajustado", "indicacao": "Edema e congestão na DRC", "advertencia": "Vigiar hipovolemia e disfunção em desidratação"},
            {"nome": "Bicarbonato de sódio", "classe": "Alcalinizante", "dose": "1-3 g/dia VO (dose diária dividida) em acidose metabólica crônica", "indicacao": "Acidose crônica com bicarbonato < 18 mEq/L", "advertencia": "Monitorar cálcio e fósforo e EAB"},
            {"nome": "Calcitriol", "classe": "Vitamina D ativa", "dose": "0,25-0,5 mcg/dia VO", "indicacao": "Hiperparatireoidismo secundário na DRC", "advertencia": "Monitorar cálcio sérico; risco de hipercalcemia"},
            {"nome": "Polímero de ligação de potássio", "classe": "Resina trocadora", "dose": "15-30 g/dia VO", "indicacao": "Hipercalemia leve a moderada", "advertencia": "Interações com outros medicamentos orais; usar com intervalo"},
            {"nome": "Ácido fólico / sulfato ferroso", "classe": "Suplementação", "dose": "Conforme carência em anemia renal", "indicacao": "Anemia da DRC em estágios pré-diálise", "advertencia": "Avaliar ferritina e saturação antes de suplementar"},
        ],
        "cids": [
            ("N18", "Doença renal crônica"), ("N19", "Insuficiência renal não especificada"),
            ("E87.6", "Hipercalemia"), ("N03", "Síndrome nefrótica"), ("R73", "Alterações da glicose (associada)"),
            ("D63", "Anemia na doença crônica"),
        ],
        "exames": [
            ("Creatinina sérica e TFG estimada", "Estadiamento da DRC (CKD-EPI)"),
            ("Relação albumina/creatinina urinária", "Albuminúria e risco de progressão"),
            ("Potássio, cálcio, fósforo e PTH", "Avaliação de complicações da DRC"),
            ("Hemograma com ferritina/saturação", "Anemia renal e reposição"),
            ("Ultrassonografia renal", "Morfologia, tamanhos e causas obstrutivas"),
        ],
        "sinais_alarme": [
            "Hipercalemia grave com ECG (ondas T apiculadas ou parada)",
            "Anúria ou oligúria progressiva com azotemia",
            "Edema agudo de pulmão e congestão refratária a diurético",
            "Creatinina subindo rapidamente (lesão renal aguda) ou + hepatites/autoimune",
            "Hemorragia digestiva com uremia (risco de sangramento por plaquetopatia)",
        ],
        "condutas": [
            ("Hipercalemia > 6,5 mEq/L", "Gluconato de cálcio EV + insulina/glicose + abordagem de eletrólitos"),
            ("DRC estágio 3 com proteinúria", "RAS + controle pressão (130/80) + estatina conforme risco"),
            ("Acidose grave (pH < 7,2)", "Bicarbonato EV e correção de causa base"),
            ("Lesão renal aguda oligúrica", "Avaliar pré-renal/renal/pós-renal; descontinuar nefrotóxicos; diálise se indicação"),
            ("Paciente em programa dialítico", "Acesso vascular, dieta e meta de fluidos em consulta com nefrologia"),
        ],
    },
    "neurologia": {
        "nome": "Neurologia (Acidente Vascular Encefálico e Cefaleias)",
        "medicamentos": [
            {"nome": "Acido acetilsalicílico", "classe": "Antiplaquetário", "dose": "100 mg/dia VO (carga 160-300 mg no AVC agudo)", "indicacao": "AVC isquêmico e prevenção secundária", "advertencia": "Contraindicado em hemorragia intracraniana ativa"},
            {"nome": "Clopidogrel", "classe": "Antiplaquetário", "dose": "75 mg/dia VO", "indicacao": "Prevenção secundária em intolerância a AAS", "advertencia": "Genótipo de metabolizador lento reduz resposta em alguns pacientes"},
            {"nome": "Sumatriptana", "classe": "Triptano", "dose": "50-100 mg VO no início da crise", "indicacao": "Crise de enxaqueca moderada a grave", "advertencia": "Contraindicado em doença coronariana e AVC prévio"},
            {"nome": "Topiramato", "classe": "Anticonvulsivante (profilaxia)", "dose": "25-100 mg/dia VO com titulação", "indicacao": "Profilaxia de enxaqueca", "advertencia": "Risco de litíase renal, alterações visuais e perda de peso"},
            {"nome": "Alteplase (rt-PA)", "classe": "Trombolítico", "dose": "0,9 mg/kg IV (máx 90 mg) com 10% em bolus", "indicacao": "AVC isquêmico dentro da janela de 4,5h", "advertencia": "Rigorosos critérios de inclusão e controle pressórico < 185/110"},
        ],
        "cids": [
            ("I63", "Infarto cerebral"), ("I61", "Hemorragia intracraniana"),
            ("G43", "Enxaqueca"), ("R51", "Cefaleia"), ("G44", "Outras síndromes de cefaleia"),
            ("I67", "Doenças cerebrovasculares"),
        ],
        "exames": [
            ("TC de crânio sem contraste", "Triagem inicial do AVC (excluir hemorragia)"),
            ("Escala NIHSS", "Gravidade do AVC e decisão de trombólise"),
            ("Angio-TC de vasos cervicais e intracranianos", "AVC em janela estendida e oclusão de grande vaso"),
            ("RM de crânio com difusão", "Confirmar isquemia aguda e infartos pequenos"),
            ("Eletroencefalograma", "Convulsões não convulsivas e estados confusionais agudos"),
        ],
        "sinais_alarme": [
            "Déficit motor/facial súbito mais de 30 minutos (protocolo de AVC)",
            "Perda de força ou fala com cefaleia súbita intensa (hemorragia subaracnóidea)",
            "Náusea/emese súbita com ataxia e nistagmo (síndrome cerebelar — AVC de fossa)",
            "Cefaleia em trovoada de início súbito, pior dor já sentida",
            "Crise epiléptica tardia (> 2 anos) ou estado de mal epiléptico",
        ],
        "condutas": [
            ("AVC isquêmico < 4,5h", "Avaliar trombólise e transporte a serviço com angio-terapêutica"),
            ("Nomear janela expandida", "Angio-TC e seleção para trombectomia mecânica (grande vaso)"),
            ("Hemorrhagia intracraniana", "Controle pressórico (PAS 140-180), neurocirurgia se expansiva"),
            ("Enxaqueca refratária aguda", "AINE + triptano + antiemético; regime de exceção em emergência"),
            ("Cefaleia em trovoada", "TC sem contraste e punção lombar se negativa (suspeitar HSA)"),
        ],
    },
    "obstetricia": {
        "nome": "Obstetrícia",
        "medicamentos": [
            {"nome": "Sulfato de magnésio", "classe": "Tocofolítico/anticonvulsivante", "dose": "4 g IV em 20 min, depois 1-2 g/h (esquema de pré-eclâmpsia)", "indicacao": "Eclâmpsia e pré-eclâmpsia grave", "advertencia": "Monitorar reflexos patelares, FR e diurese; antagonista: gluconato de cálcio"},
            {"nome": "Nifedipino", "classe": "Bloqueador de canal de cálcio", "dose": "10 mg VO a cada 20-30 min até alvo, máx. 50 mg", "indicacao": "Crise hipertensiva na gestação", "advertencia": "Evitar sublingual; monitorar PA de material"},
            {"nome": "Ocitocina", "classe": "Hormônio/utero-tônico", "dose": "10-20 UI em soro pós-parto; indução conforme esquema", "indicacao": "Prevenção/tratamento de hemorragia pós-parto e indução", "advertencia": "Risco de hiperestimulação; monitorar contrações e bem-estar fetal"},
            {"nome": "Misoprostol", "classe": "Prostaglandina E1", "dose": "600-1000 mcg RETAL na HPP atônica (após ocitocina)", "indicacao": "Hemorragia pós-parto por atonia", "advertencia": "Contraindicado em cicatriz uterina (indução)"},
            {"nome": "Ácido tranexâmico", "classe": "Antifibrinolítico", "dose": "1 g IV em 10 min, repetir se necessário", "indicacao": "Hemorragia pós-parto (dentro de 3h)", "advertencia": "Iniciar precoce; contraindicado se coagulopatia grave não tratável"},
        ],
        "cids": [
            ("O14", "Pré-eclâmpsia"), ("O88", "Embolia obstétrica"), ("O72", "Hemorragia pós-parto"),
            ("O24", "Diabetes gestacional"), ("O60", "Trabalho de parto prematuro"), ("O26", "Cuidados da gestante de alto risco"),
        ],
        "exames": [
            ("PA e proteinúria (fita ou RPCU)", "Rastreio de pré-eclâmpsia"),
            ("USG obstétrica (idade gestacional e morfológica)", "datagem e rastreio de anomalias"),
            ("Glicemia de jejum / TOTG 75g", "Rastreio de diabetes gestacional (24-28 semanas)"),
            ("Cardiotocografia anteparto", "Vitalidade fetal em gestações de risco"),
            ("Hemograma, plaquetas e função hepática", "Avaliação de pré-eclâmpsia grave e HELLP"),
        ],
        "sinais_alarme": [
            "Cefaleia frontal, escotomas, epigastralgia e PA sistólica ≥ 160 (pré-eclâmpsia grave)",
            "Hemorragia vaginal intensa em qualquer trimestre",
            "Dor abdominal intensa/fetal com sofrimento fetal agudo",
            "Perda de líquido amniótico com febre (corioamnionite)",
            "Movimentação fetal reduzida",
        ],
        "condutas": [
            ("Pré-eclâmpsia grave / eclâmpsia", "Sulfato de magnésio + antihipertensivo + resolução da gestação após estabilização"),
            ("Hemorragia pós-parto", "Protocolo PPH: ocitocina + ácido tranexâmico + misoprostol + identificar causa (4T)"),
            ("Diabetes gestacional", "Meta glicêmica (jejum ≤ 95); metformina/insulina se não atingir"),
            ("Trabalho de parto prematuro", "Corticoide (betametasona) + tocólise se indicado + referência ao alto risco"),
            ("Corioamnionite", "Antibioticoterapia IV + resolução do parto o mais breve possível"),
        ],
    },
    "pediatria": {
        "nome": "Pediatria",
        "medicamentos": [
            {"nome": "Salbutamol inalatório", "classe": "Beta-2 agonista", "dose": "2-6 jatos com espaçador (ASMA aguda) ou nebulização", "indicacao": "Crise de asma/broncoespasmo em crianças", "advertencia": "Pode causar taquicardia e tremor; monitorar resposta"},
            {"nome": "Soro de reidratação oral (SRO)", "classe": "Solução oral", "dose": "50-100 mL/kg na reidratação, depois 10 mL/kg após cada evacuação", "indicacao": "Desidratação por diarreia/vômitos", "advertencia": "Preferir VO quando leve-moderada; EV nas graves"},
            {"nome": "Amoxicilina", "classe": "Aminopenicilina", "dose": "50 mg/kg/dia dividido em 2-3 tomadas", "indicacao": "Otite média aguda e amigdalite bacteriana", "advertencia": "Reavaliar em 48-72h; não indicado em infecções virais"},
            {"nome": "Paracetamol", "classe": "Analgésico/antitérmico", "dose": "10-15 mg/kg/dose a cada 4-6h", "indicacao": "Febre e dor", "advertencia": "Não exceder 60 mg/kg/dia; risco de hepatotoxicidade"},
            {"nome": "Ibuprofeno", "classe": "AINE", "dose": "5-10 mg/kg/dose a cada 6-8h", "indicacao": "Febre e dor inflamatória", "advertencia": "Evitar < 6 meses e em desidratação"},
        ],
        "cids": [
            ("J21", "Bronquiolite aguda"), ("A09", "Gastroenterite diarreica aguda"),
            ("H66", "Otite média aguda"), ("J03", "Amigdalite aguda"),
            ("J45", "Asma"), ("E86", "Hipovolemia/desidratação"),
        ],
        "exames": [
            ("Oximetria de pulso", "Avaliação de hipoxemia na bronquiolite e crises de asma"),
            ("Radiografia de tórax", "Suspeita de complicação ou pneumonia bacteriana"),
            ("Eletrólitos e glicemia na desidratação", "Avaliação metabólica de casos moderados-graves"),
            ("Teste rápido de antígeno estreptocócico", "Amigdalite com critérios (Centor)"),
            ("Urina I e urocultura", "ITU febril na criança (sempre pensar em criança < 2 anos febris)"),
        ],
        "sinais_alarme": [
            "Bronquiolite com cianose, gemência, esforço respiratório intenso ou O2 < 92%",
            "Desidratação grave: letargia, olhos fundos, turgor viscoso, pulso fino",
            "Febre em criança < 3 meses (sempre investigar sepse) ",
            "Criança com choro inconsolável, abaulamento de fontanela ou convulsão",
            "Vômitos incoercíveis ou sinais de invaginação (evacuação com sangue, dor abdominal) ",
        ],
        "condutas": [
            ("Bronquiolite leve sem hipoxemia", "Suporte, hidratação, monitorar alimentação; evitar exames desnecessários"),
            ("Crise asmática grave", "Salbutamol + corticosteroide oral + O2, monitorar resposta em 1h"),
            ("Desidratação leve-moderada", "SRO 50-100 mL/kg e reavaliação; observar em domicílio com orientação"),
            ("Febre em lactente < 3 meses", "Investigar: hemograma, urocultura, punção lombar conforme protocolo local"),
            ("Amigdalite com critérios de Centor", "Amoxicilina por 10 dias; alívio com paracetamol/ibuprofeno"),
        ],
    },
    "psiquiatria": {
        "nome": "Psiquiatria",
        "medicamentos": [
            {"nome": "Sertralina", "classe": "ISRS", "dose": "50 mg/dia VO, podendo titular a 200 mg", "indicacao": "Transtorno depressivo maior e TAG", "advertencia": "Primeiras semanas: risco de ideação suicida em jovens; síndrome serotoninérgica"},
            {"nome": "Escitalopram", "classe": "ISRS", "dose": "10 mg/dia VO, máx. 20 mg", "indicacao": "Depressão e ansiedade generalizada", "advertencia": "Menor risco de interações; efeitos gastrointestinais iniciais"},
            {"nome": "Mirtazapina", "classe": "NaSSA", "dose": "15-45 mg/dia à noite", "indicacao": "Depressão com insônia e perda de apetite", "advertencia": "Risco de sedação e ganho de peso; agranulocitose rara"},
            {"nome": "Risperidona", "classe": "Antipsicótico atípico", "dose": "1-6 mg/dia VO", "indicacao": "Esquizofrenia e psicose", "advertencia": "Hiperprolactinemia, síndrome metabólica e sintomas extrapiramidais"},
            {"nome": "Haloperidol", "classe": "Antipsicótico típico", "dose": "2-10 mg/dia VO ou IM em agitação", "indicacao": "Psicose e agitação psicomotora", "advertencia": "Risco de distonia aguda e síndrome extrapiramidal tardia"},
        ],
        "cids": [
            ("F32", "Transtorno depressivo maior"), ("F41.1", "Transtorno de ansiedade generalizada"),
            ("F20", "Esquizofrenia"), ("F43.1", "Transtorno de estresse pós-traumático"),
            ("F10-F19", "Transtornos por uso de substâncias"), ("F31", "Transtorno bipolar"),
        ],
        "exames": [
            ("Escala PHQ-9", "Triagem e gravidade da depressão"),
            ("Mini-exame mental", "Déficit cognitivo em idosos com queixas depressivas"),
            ("TSH, B12, glicemia, eletrólitos", "Excluir causas orgânicas de sintomas psiquiátricos"),
            ("ECG e exames cardiológicos em drogas QT", "Pré-tratamento com antipsicóticos de risco"),
            ("Teste toxicológico de urina", "Quando suspeita de uso de substâncias"),
        ],
        "sinais_alarme": [
            "Ideação ou plano suicida ativo com histórico de tentativa",
            "Síndrome serotoninérgica: clônus, hipertermia, rigidez, agitação",
            "Síndrome neuroléptica maligna: rigidez + hipertermia + CPK alto",
            "Manía com psicose, agitação extrema e agressividade",
            "Psicose primeira com risco de dano a terceiros ou deterioração funcional grave",
        ],
        "condutas": [
            ("Risco suicida iminente", "Hospitalização; avaliar supervisão contínua e envolver família"),
            ("Depressão leve a moderada", "Psicoterapia + ISRS (sertralina/escitalopram) com reavaliação em 2-4 semanas"),
            ("Síndrome neuroléptica maligna", "Suspender antipsicótico, suporte, bromocriptina em caso grave"),
            ("Manía aguda", "Estabilizador de humor + antipsicótico e hospitalização quando necessária"),
            ("Transtorno de pânico/TAG", "ISRS + psicoeducação; evitar benzodiazepínicos prolongados"),
        ],
    },
    "reumatologia": {
        "nome": "Reumatologia",
        "medicamentos": [
            {"nome": "Alopurinol", "classe": "Inibidor de xantina oxidase", "dose": "100-300 mg/dia VO (titular pelo urato)", "indicacao": "Gota: prevenção de crises a longo prazo", "advertencia": "Iniciar após crise resolver; titular e associar colchicina profilática; alerta de síndrome de hipersensibilidade"},
            {"nome": "Colchicina", "classe": "Anti-inflamatório", "dose": "1,0 mg na crise e 0,5 mg após 1h (ou 0,5 mg 2x/dia profilática)", "indicacao": "Gota aguda e profilaxia nas trocas de urato", "advertencia": "Toxicidade gastrointestinal e hematológica; ajustar em DRC"},
            {"nome": "Prednisona", "classe": "Glicocorticoide", "dose": "Crise de gota: 0,5 mg/kg/dia por 5-7 dias; lúpus: 0,5-1 mg/kg/dia conforme gravidade", "indicacao": "Doenças inflamatórias (gota aguda, lúpus ativo)", "advertencia": "Cálcio/vit D, controle glicêmico e densidade óssea em uso prolongado"},
            {"nome": "Hidroxicloroquina", "classe": "Antimalárico/antirreumático", "dose": "200-400 mg/dia VO", "indicacao": "LES e artrite/pletora de sintomas", "advertencia": "Monitorar retina (risco de retinopatia em uso prolongado)"},
            {"nome": "Azatioprina", "classe": "Imunossupressor", "dose": "1-2,5 mg/kg/dia VO", "indicacao": "LES e dermatomiosite moderadas", "advertencia": "Monitorar hematológico; medir TPMT antes do início"},
        ],
        "cids": [
            ("M10", "Gota"), ("M32", "Lúpus eritematoso sistêmico"), ("M33", "Dermatomiosite/polimiosite"),
            ("M05", "Artrite reumatoide soropositiva"), ("M35", "Síndromes de sobreposição"), ("R29", "Poliartralgia"),
        ],
        "exames": [
            ("Urato sérico e ácido úrico urinário", "Diagnóstico e monitoramento da gota"),
            ("Biópsia/aspiração articular (cristais)", "Confirmação da gota (cristais em agulha)"),
            ("FAN, anti-dsDNA e complemento", "Diagnóstico e atividade do LES"),
            ("Proteína C reativa, VHS e hemograma", "Atividade inflamatória e hematológica no LES"),
            ("Cilindrúria e proteinúria de 24h", "Avaliação renal (nefrite lúpica)"),
        ],
        "sinais_alarme": [
            "Artrite aguda monoarticular com febre (excluir artrite séptica)",
            "Lúpus com nefrite (hematúria, proteinúria, hipertensão) ou neuropsiquiátrico",
            "Rash malar + febre em mulher jovem com pancitopenia",
            "Dor articular grave + hiperestesia generalizada em paciente imunossuprimido",
            "Síndrome de sobreposição com hemorragia alveolar",
        ],
        "condutas": [
            ("Gota aguda", "Colchicina ou AINE/esteroide por 5-7 dias; não iniciar urato hipouricemiante na crise"),
            ("Nefrite lúpica classe III/IV", "Pulso de corticoide + imunossupressor com reumatologia e nefrologia"),
            ("Artrite séptica suspeita", "Punção articular + antibiótico EV + cirurgia/artrotomia se torácica clássica"),
            ("Prevenção de crise de gota em início de urato", "Colchicina profilática por 6 meses + titulação lenta"),
            ("Lúpus leve (cutâneo/artr)", "Hidroxicloroquina + filtro solar + AINE curto"),
        ],
    },
}


def _slug(nome: str) -> str:
    import unicodedata

    normalizado = unicodedata.normalize("NFKD", nome)
    sem_acentos = "".join(c for c in normalizado if not unicodedata.combining(c))
    return (
        sem_acentos.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("(", "")
        .replace(")", "")
    )


def _paragrafos_manual(esp: dict) -> list[tuple[str, str]]:
    """Retorna [(título, [lista de blocos de texto])] do manual de condutas."""
    nome = esp["nome"]
    cids = ", ".join(f"{c} - {d}" for c, d in esp["cids"])
    exames = "".join(f"<br/><b>{e}</b>: {i}" for e, i in esp["exames"])
    alarmes = "".join(f"<br/>• {a}" for a in esp["sinais_alarme"])
    condutas = "".join(f"<br/>• <b>{s}</b>: {c}" for s, c in esp["condutas"])
    secoes = [
        ("apresentacao", [
            f"Manual de condutas em {nome}. Material didático sintético: conteúdo plausível "
            f"baseado em práticas reconhecidas, porém NÃO é publicação oficial e não deve "
            f"nortear decisão clínica real. Objetivo: apoiar o fluxo de cuidado inicial e o "
            f"encaminhamento do paciente na atenção primária.",
        ]),
        ("condicoes", [
            f"Principais condições clínicas abordadas em {nome} e seus códigos CID-10: {cids}.",
            "A classificação da condição orienta a conduta inicial, a necessidade de exames "
            "complementares e o nível de urgência do encaminhamento.",
        ]),
        ("diagnostico", [
            "Exames e ferramentas usualmente empregados para diagnóstico e acompanhamento:",
            exames,
            "A solicitação deve considerar sempre a relação custo-benefício e o contexto do paciente. "
            "Resultados alterados devem ser correlacionados com o quadro clínico antes de mudanças de conduta.",
        ]),
        ("condutas", [
            "Principais condutas e critérios de escalonamento:",
            condutas,
            "Esquemas detalhados de prescrição encontram-se no Guia de Prescrição correspondente e "
            "nas tabelas de posologia (planilha anexa).",
        ]),
        ("alarmes", [
            "Sinais de alarme que indicam gravidade e necessidade de encaminhamento imediato ou "
            "avaliação especializada:",
            alarmes,
            "Quando um sinal de alarme estiver presente, priorizar a estabilização, o acesso à "
            "urgencência e o contato com o serviço de referência.",
        ]),
    ]
    return secoes


def _paragrafos_guia(esp: dict) -> list[tuple[str, str]]:
    """Parágrafos do guia de prescrição (1 bloco por medicamento, com dose)."""
    nome = esp["nome"]
    blocos = [("introducao", [
        f"Guia de prescrição em {nome}. Material didático sintético — dosagens apresentadas "
        f"correspondem a faixas usuais; em prática real, confirmar bula/atualizações e considerar "
        f"função renal, hepática, idade e interações. Confirmar a presente versão do medicamento.",
    ])]
    for med in esp["medicamentos"]:
        if med["dose"] == "—":
            continue
        blocos.append((f"med-{med['nome']}", [
            f"<b>{med['nome']}</b> ({med['classe']}). <b>Dose:</b> {med['dose']}. "
            f"<b>Indicação:</b> {med['indicacao']}. <b>Atenção:</b> {med['advertencia']}.",
            "Prescrição deve vir acompanhada de orientações de adesão, sinais de toxicidade e "
            "necessidade de reavaliação; revisar dose em idosos e ajustes por função renal.",
        ]))
    return blocos


def _paragrafos_protocolo(esp: dict) -> list[tuple[str, str]]:
    """Parágrafos do protocolo de atendimento (fluxo de urgência)."""
    nome = esp["nome"]
    alarmes = "".join(f"<br/>• {a}" for a in esp["sinais_alarme"])
    condutas = "".join(f"<br/>• <b>{s}</b>: {c}" for s, c in esp["condutas"])
    return [
        ("objetivo", [
            f"Protocolo de atendimento em {nome}. Materiais didáticos sintéticos para fluxos de "
            f"acolhimento com classificação de risco e condução inicial na emergência.",
        ]),
        ("triagem", [
            "Acolhimento: identificar pacientes com sinais de gravidade na entrada (sinais de alarme "
            "abaixo) e priorizá-los.",
            alarmes,
        ]),
        ("fluxo", [
            "Fluxo de condutas:",
            condutas,
            "Sempre reavaliar o paciente após cada intervenção; registrar sinais vitais, exames e "
            "decisões no prontuário; garantir transferência segura quando necessário.",
        ]),
        ("contrareferencia", [
            "Ao alta da unidade de urgência, orientar retorno programado, ajuste de medicação de "
            "manutenção e sinais que exigem nova avaliação imediata.",
        ]),
    ]


def _gerar_pdf_secoes(caminho: Path, titulo: str, secoes: list[tuple[str, str]]) -> int:
    """Gera um PDF multi-página; cada seção é uma página (ou mais)."""
    import reportlab.lib.pagesizes as pagesizes
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=pagesizes.A4,
        title=titulo,
        author=AUTOR_DIDATICO,
    )
    estilo_titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=16, spaceAfter=12)
    estilo_sub = ParagraphStyle("sub", fontName="Helvetica-Bold", fontSize=12, spaceAfter=8)
    estilo_corpo = ParagraphStyle("corpo", fontName="Helvetica", fontSize=11, leading=15, spaceAfter=10)

    historia: list = [Paragraph(titulo, estilo_titulo)]
    paginas = 1
    for nome_secao, textos in secoes:
        historia.append(Spacer(1, 6))
        historia.append(Paragraph(nome_secao.replace("-", " ").title(), estilo_sub))
        for texto in textos:
            historia.append(Paragraph(texto, estilo_corpo))
        historia.append(PageBreak())
        paginas += 1
    doc.build(historia)
    return paginas


def gerar_pdf_manual(esp: dict, pdf_dir: Path) -> Path:
    slug = _slug(esp["nome"].split(" ")[0]) if esp["nome"].startswith("Neurologia") else _slug(esp["nome"])
    caminho = pdf_dir / f"manual_condutas_{slug}.pdf"
    _gerar_pdf_secoes(caminho, f"Manual de Condutas em {esp['nome']}", _paragrafos_manual(esp))
    return caminho


def gerar_pdf_guia(esp: dict, pdf_dir: Path) -> Path:
    slug = _slug(esp["nome"].split(" ")[0]) if esp["nome"].startswith("Neurologia") else _slug(esp["nome"])
    caminho = pdf_dir / f"guia_prescricao_{slug}.pdf"
    _gerar_pdf_secoes(caminho, f"Guia de Prescrição em {esp['nome']}", _paragrafos_guia(esp))
    return caminho


def gerar_pdf_protocolo(esp: dict, pdf_dir: Path) -> Path:
    slug = _slug(esp["nome"].split(" ")[0]) if esp["nome"].startswith("Neurologia") else _slug(esp["nome"])
    caminho = pdf_dir / f"protocolo_atendimento_{slug}.pdf"
    _gerar_pdf_secoes(caminho, f"Protocolo de Atendimento em {esp['nome']}", _paragrafos_protocolo(esp))
    return caminho


def gerar_excel(esp: dict, excel_dir: Path) -> Path:
    slug = _slug(esp["nome"].split(" ")[0]) if esp["nome"].startswith("Neurologia") else _slug(esp["nome"])
    caminho = excel_dir / f"posologia_{slug}.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)

    ws_med = wb.create_sheet(title="Medicamentos")
    ws_med.append(["Farmaco", "Classe", "Dose", "Indicacao", "Atencao/Advertencia"])
    for med in esp["medicamentos"]:
        if med["dose"] == "—":
            continue
        ws_med.append([med["nome"], med["classe"], med["dose"], med["indicacao"], med["advertencia"]])

    ws_cid = wb.create_sheet(title="Diagnosticos")
    ws_cid.append(["CID-10", "Descricao"])
    for codigo, desc in esp["cids"]:
        ws_cid.append([codigo, desc])

    ws_ex = wb.create_sheet(title="Exames")
    ws_ex.append(["Exame/Instrumento", "Indicacao"])
    for ex, indic in esp["exames"]:
        ws_ex.append([ex, indic])

    wb.save(str(caminho))
    return caminho


def _merge_metadados(entradas: dict[str, dict]) -> None:
    existente: dict = {}
    if METADADOS.is_file():
        try:
            existente = json.loads(METADADOS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existente = {}
    fontes = existente.get("fontes", {})
    for nome, meta in entradas.items():
        fontes[nome] = meta
    METADADOS.write_text(
        json.dumps(
            {
                "versao": 1,
                "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "fontes": dict(sorted(fontes.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _meta_sintetica(caminho: Path, titulo: str, tipo: str) -> dict:
    return {
        "title": titulo,
        "author": AUTOR_DIDATICO,
        "institution": "Material didático sintético",
        "year": "2024",
        "document_type": tipo,
        "license": LICENCA_SINTETICA,
        "sintetico": True,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Gera corpus sintético de conhecimento por especialidade.")
    parser.add_argument("--especialidades", type=str, default=None,
                        help="Lista separada por vírgula; padrão: todas as especialidades.")
    args = parser.parse_args()

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)

    selecionadas = args.especialidades.split(",") if args.especialidades else list(ESPECIALIDADES)
    entradas: dict[str, dict] = {}
    total_pdf = 0
    for key in selecionadas:
        if key not in ESPECIALIDADES:
            print(f"[aviso] especialidade desconhecida: {key}")
            continue
        esp = ESPECIALIDADES[key]
        slug = _slug(esp["nome"].split(" ")[0]) if esp["nome"].startswith("Neurologia") else _slug(esp["nome"])
        manual = gerar_pdf_manual(esp, PDF_DIR)
        guia = gerar_pdf_guia(esp, PDF_DIR)
        protocolo = gerar_pdf_protocolo(esp, PDF_DIR)
        excel = gerar_excel(esp, EXCEL_DIR)
        total_pdf += 3
        entradas[manual.name] = _meta_sintetica(manual, f"Manual de Condutas em {esp['nome']}", "manual_didatico")
        entradas[guia.name] = _meta_sintetica(guia, f"Guia de Prescrição em {esp['nome']}", "guia_prescricao")
        entradas[protocolo.name] = _meta_sintetica(protocolo, f"Protocolo de Atendimento em {esp['nome']}", "protocolo_didatico")
        entradas[excel.name] = _meta_sintetica(excel, f"Tabelas de Posologia - {esp['nome']}", "tabela_posologia")
        print(f"[ok] {esp['nome']}: {manual.name}, {guia.name}, {protocolo.name}, {excel.name}")

    _merge_metadados(entradas)
    print(f"\nGerados: {total_pdf} PDFs + {len(selecionadas)} planilhas em {PDF_DIR} e {EXCEL_DIR}.")
    print(f"Metadados atualizados em {METADADOS} (sintetico=True).")


if __name__ == "__main__":
    main()