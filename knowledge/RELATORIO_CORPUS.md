# Relatório do Corpus de Conhecimento (RAG)

Gerado em: 05/09/2026 22:18 · Coleção: `assistente_medico_conhecimento_text-embedding-3-small` (e demais `*_conhecimento_*`)

## Resumo

| Métrica | Valor |
|---|---:|
| Fontes documentais catalogadas | 65 |
| Chunks totais no vector store | **9.126** |
| — chunks de PDF | 9.078 |
| — chunks de planilha (Excel) | 48 |
| — chunks de fontes reais (PCDTs/manuais MS) | 8.894 |
| — chunks de fontes sintéticas (mock didático) | 232 |

**Alvo da especificação (5.000–15.000 chunks): DENTRO do alvo de 5.000 a 15.000 chunks.**

## Fontes (fonte a fonte)

| Fonte | Título | Instituição | Ano | Tipo | Sintético | Chunks |
|---|---|---|---|---|---|---:|
| `livro_pcdt_volume_iii_2014.pdf` | Protocolos Clínicos e Diretrizes Terapêuticas do Ministério da Saúde (Volume III) | Ministério da Saúde (Conitec) | 2014 | livro_pcdt | — | 2.781 |
| `pcdt_sobrepeso_obesidade_2020.pdf` | Protocolo Clínico e Diretrizes Terapêuticas de Sobrepeso e Obesidade em Adultos | Ministério da Saúde (Conitec) | 2020 | pcdt | — | 1.119 |
| `pcdt_artrite_reumatoide.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Artrite Reumatoide | Ministério da Saúde (Conitec) | 2021 | pcdt | — | 600 |
| `politica_nacional_atencao_urgencias_3ed.pdf` | Política Nacional de Atenção às Urgências (3ª edição) | Ministério da Saúde (BVS-MS) | 2006 | manual | — | 519 |
| `pcdt_esclerose_multipla_2024.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Esclerose Múltipla | Ministério da Saúde (Conitec) | 2024 | pcdt | — | 438 |
| `pcdt_hepatite_b_2016.pdf` | Relatório de Recomendação PCDT Hepatite B e Coinfecções | Ministério da Saúde (Conitec) | 2016 | relatorio_pcdt | — | 438 |
| `pcdt_hipertensao_2025.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Hipertensão Arterial Sistêmica | Ministério da Saúde (Conitec) | 2025 | pcdt | — | 396 |
| `pcdt_hiv_modulo2_2024.pdf` | Protocolo Clínico e Diretrizes Terapêuticas para Manejo da Infecção pelo HIV (Módulo 2) | Ministério da Saúde (Departamento de HIV/Aids) | 2024 | pcdt | — | 390 |
| `regulacao_medica_urgencias.pdf` | Regulação Médica das Urgências (Ministério da Saúde) | Ministério da Saúde (BVS-MS) | 2014 | manual | — | 385 |
| `pcdt_asma_2021.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Asma | Ministério da Saúde (Conitec) | 2021 | pcdt | — | 362 |
| `pcdt_diabete_melito_tipo2_2026.pdf` | Protocolo Clínico e Diretrizes Terapêuticas do Diabete Melito Tipo 2 | Ministério da Saúde (Conitec) | 2026 | pcdt | — | 318 |
| `pcdt_dpoc_2021.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Doença Pulmonar Obstrutiva Crônica (Relatório de Recomendação nº 651) | Ministério da Saúde (Conitec) | 2021 | pcdt | — | 318 |
| `pcdt_parkinson.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Doença de Parkinson | Ministério da Saúde (Conitec) | 2022 | pcdt | — | 290 |
| `pcdt_epilepsia.pdf` | Protocolo Clínico e Diretrizes Terapêuticas da Epilepsia | Ministério da Saúde (Conitec) | 2019 | pcdt | — | 273 |
| `manual_instrutivo_rue.pdf` | Manual Instrutivo da Rede de Atenção às Urgências e Emergências no SUS | Ministério da Saúde (protocolo aprovado) | 2013 | manual | — | 233 |
| `pcdt_diabete_melito_tipo1_resumido.pdf` | Protocolo Clínico e Diretrizes Terapêuticas do Diabete Melito Tipo 1 (versão resumida) | Ministério da Saúde (Conitec) | 2019 | pcdt | — | 18 |
| `pcdt_glaucoma_resumido.pdf` | Protocolo Clínico e Diretrizes Terapêuticas do Glaucoma (versão resumida) | Ministério da Saúde (Conitec) | 2020 | pcdt | — | 16 |
| `guia_prescricao_cardiologia.pdf` | Guia de Prescrição em Cardiologia | Material didático sintético | 2024 | guia_prescricao | sim | 7 |
| `guia_prescricao_dermatologia.pdf` | Guia de Prescrição em Dermatologia | Material didático sintético | 2024 | guia_prescricao | sim | 7 |
| `guia_prescricao_infectologia.pdf` | Guia de Prescrição em Infectologia | Material didático sintético | 2024 | guia_prescricao | sim | 7 |
| `guia_prescricao_nefrologia.pdf` | Guia de Prescrição em Nefrologia | Material didático sintético | 2024 | guia_prescricao | sim | 7 |
| `guia_prescricao_endocrinologia.pdf` | Guia de Prescrição em Endocrinologia | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_gastroenterologia.pdf` | Guia de Prescrição em Gastroenterologia | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_geriatria.pdf` | Guia de Prescrição em Geriatria | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_neurologia.pdf` | Guia de Prescrição em Neurologia (Acidente Vascular Encefálico e Cefaleias) | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_obstetricia.pdf` | Guia de Prescrição em Obstetrícia | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_pediatria.pdf` | Guia de Prescrição em Pediatria | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_psiquiatria.pdf` | Guia de Prescrição em Psiquiatria | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `guia_prescricao_reumatologia.pdf` | Guia de Prescrição em Reumatologia | Material didático sintético | 2024 | guia_prescricao | sim | 6 |
| `manual_condutas_cardiologia.pdf` | Manual de Condutas em Cardiologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_dermatologia.pdf` | Manual de Condutas em Dermatologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_endocrinologia.pdf` | Manual de Condutas em Endocrinologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_gastroenterologia.pdf` | Manual de Condutas em Gastroenterologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_geriatria.pdf` | Manual de Condutas em Geriatria | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_infectologia.pdf` | Manual de Condutas em Infectologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_nefrologia.pdf` | Manual de Condutas em Nefrologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_neurologia.pdf` | Manual de Condutas em Neurologia (Acidente Vascular Encefálico e Cefaleias) | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_obstetricia.pdf` | Manual de Condutas em Obstetrícia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_pediatria.pdf` | Manual de Condutas em Pediatria | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_psiquiatria.pdf` | Manual de Condutas em Psiquiatria | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `manual_condutas_reumatologia.pdf` | Manual de Condutas em Reumatologia | Material didático sintético | 2024 | manual_didatico | sim | 5 |
| `posologia_geriatria.xlsx` | Tabelas de Posologia - Geriatria | Material didático sintético | 2024 | tabela_posologia | sim | 5 |
| `posologia_cardiologia.xlsx` | Tabelas de Posologia - Cardiologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_dermatologia.xlsx` | Tabelas de Posologia - Dermatologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_endocrinologia.xlsx` | Tabelas de Posologia - Endocrinologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_gastroenterologia.xlsx` | Tabelas de Posologia - Gastroenterologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_infectologia.xlsx` | Tabelas de Posologia - Infectologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_nefrologia.xlsx` | Tabelas de Posologia - Nefrologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_neurologia.xlsx` | Tabelas de Posologia - Neurologia (Acidente Vascular Encefálico e Cefaleias) | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_obstetricia.xlsx` | Tabelas de Posologia - Obstetrícia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_pediatria.xlsx` | Tabelas de Posologia - Pediatria | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `posologia_reumatologia.xlsx` | Tabelas de Posologia - Reumatologia | Material didático sintético | 2024 | tabela_posologia | sim | 4 |
| `protocolo_atendimento_cardiologia.pdf` | Protocolo de Atendimento em Cardiologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_dermatologia.pdf` | Protocolo de Atendimento em Dermatologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_endocrinologia.pdf` | Protocolo de Atendimento em Endocrinologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_gastroenterologia.pdf` | Protocolo de Atendimento em Gastroenterologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_geriatria.pdf` | Protocolo de Atendimento em Geriatria | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_infectologia.pdf` | Protocolo de Atendimento em Infectologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_nefrologia.pdf` | Protocolo de Atendimento em Nefrologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_neurologia.pdf` | Protocolo de Atendimento em Neurologia (Acidente Vascular Encefálico e Cefaleias) | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_obstetricia.pdf` | Protocolo de Atendimento em Obstetrícia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_pediatria.pdf` | Protocolo de Atendimento em Pediatria | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_psiquiatria.pdf` | Protocolo de Atendimento em Psiquiatria | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `protocolo_atendimento_reumatologia.pdf` | Protocolo de Atendimento em Reumatologia | Material didático sintético | 2024 | protocolo_didatico | sim | 4 |
| `posologia_psiquiatria.xlsx` | Tabelas de Posologia - Psiquiatria | Material didático sintético | 2024 | tabela_posologia | sim | 3 |

## Distribuição por instituição

| Instituição | Chunks |
|---:|---:|
| Ministério da Saúde (Conitec) | 7.367 |
| Ministério da Saúde (BVS-MS) | 904 |
| Ministério da Saúde (Departamento de HIV/Aids) | 390 |
| Ministério da Saúde (protocolo aprovado) | 233 |
| Material didático sintético | 232 |

## Distribuição por ano

| Ano | Chunks |
|---:|---:|
| 2026 | 318 |
| 2025 | 396 |
| 2024 | 1.060 |
| 2022 | 290 |
| 2021 | 1.280 |
| 2020 | 1.135 |
| 2019 | 291 |
| 2016 | 438 |
| 2014 | 3.166 |
| 2013 | 233 |
| 2006 | 519 |

## Distribuição por tipo de documento

| Tipo | Chunks |
|---:|---:|
| pcdt | 4.538 |
| livro_pcdt | 2.781 |
| manual | 1.137 |
| relatorio_pcdt | 438 |
| guia_prescricao | 76 |
| manual_didatico | 60 |
| protocolo_didatico | 48 |
| tabela_posologia | 48 |

## Rastreabilidade e reprodutibilidade

- **Fontes reais**: curadas e baixadas por
  `database/conhecimento/baixar_fontes_reais.py` (validação de `%PDF`, múltiplas
  URLs com fallback). O catálogo com título/autor/instituição/ano/licença/URL de
  cada fonte está em `knowledge/metadados_fontes.json` (versionado).
- **Fontes sintéticas**: geradas por
  `database/conhecimento/gerar_dataset_conhecimento.py` (12 especialidades ×
  manual + guia de prescrição + protocolo de atendimento + tabela de posologia).
  Todo chunk sintético carrega `sintetico: true` e licença didática.
- **Ingestão**: `python database/conhecimento/ingestao_conhecimento.py
  --provider mock --knowledge-dir knowledge --reset-colecao`. O processo é
  idempotente (chunk_id estável = fonte + localização + hash do conteúdo).
- **Relatório**: `python database/conhecimento/gerar_relatorio_corpus.py`.

Para o **provedor OpenAI** (produção), repetir a ingestão com `--provider openai`
(embeddings com 1536 dimensões em uma coleção separada) e regenerar este
relatório com `--provider openai`.

## Consultas de validação sugeridas

Consultas de teste para conferir que o corpus recupera o contexto esperado na
API/UI (o resultado real depende do provedor de embeddings em uso):

| Consulta | Fontes esperadas no contexto |
|---|---|
| "Hipertensão arterial sistêmica medicamentos de primeira linha" | `pcdt_hipertensao_2025.pdf` |
| "Crise asmática salbutamol dose" | `pcdt_asma_2021.pdf` |
| "Conduta na pré-eclâmpsia grave sulfato de magnésio" | `manual_condutas_obstetricia.pdf` (sintético) |
| "Metformina no diabete melito tipo 2" | `pcdt_diabete_melito_tipo2_2026.pdf` |
| "Posologia de medicamentos em pediatria" | `posologia_pediatria.xlsx` (sintético) |
| "Linhas de organização da Rede de Atenção às Urgências" | `manual_instrutivo_rue.pdf`, `politica_nacional_atencao_urgencias_3ed.pdf` |

Toda resposta do agente deve citar a fonte (`source`/`document_title`/`page`);
o corpus foi desenhado para tornar essas citações rastreáveis até o arquivo
original.
