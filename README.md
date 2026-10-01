## Objetivo

Construir uma base integrada que permita responder duas perguntas:

1. **Como os desastres afetam os municípios?** Impactos em indicadores
   sociais, como população afetada, moradias danificadas e serviços
   essenciais interrompidos.
2. **Quem está mais exposto?** Como a ocorrência e a gravidade dos desastres
   se distribuem de acordo com índices sociais (renda, IDH, saneamento,
   vulnerabilidade social etc.).

A primeira etapa, concluída, é o pipeline de desastres (Atlas Digital).
As próximas integram dados socioeconômicos municipais ao mesmo warehouse.

## Roadmap

- [x] Coleta e limpeza do Atlas Digital de Desastres
- [x] Data warehouse SQLite (Staging → Silver → Gold)
- [x] Primeiro mapa do Brasil
- [ ] Integração de indicadores municipais, usando o código IBGE do município como chave
- [ ] Análise de desastres por bioma
- [ ] Cruzamento desastres × índices sociais
- [ ] Mapeamento dos resultados para os ODS relacionados

Mapa atual Tableau : https://public.tableau.com/app/profile/henrique.prado3223/viz/Mapabrasa/Planilha1
