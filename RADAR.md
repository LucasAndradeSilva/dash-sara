# Radar Pastoral

Painel da Sara Nossa Terra — Morumbi Sul para acompanhar visitantes e participação nos cultos.

## Atualizar o painel

O gerador mantém `index.html`, `dashboard-visitantes.html` e `dashboard-data.json` sincronizados:

```sh
python build_dashboard.py
node --test tests/radar.test.cjs
```

Requer Python com pandas e openpyxl. A interface e o Chart.js são embutidos no HTML; não há dependência de CDN. O logotipo é o arquivo local `logo.jpg`.

- `template.html`: estrutura e conteúdo da interface.
- `radar.css`: identidade visual e layouts para computador e celular.
- `radar.js`: filtros, gráficos, visitantes e exportações.
- As duas planilhas e o CSV continuam sendo as fontes de dados.

## Leitura dos indicadores

**Registros** são entradas de visita; **pessoas únicas** usam telefone normalizado, ou nome quando não há telefone. Telefones compartilhados podem agrupar pessoas. As fontes não são alteradas por essa identificação.

**Novos no período** considera a primeira data de visita em todo o histórico disponível, independentemente do filtro de culto. **Pessoas que retornaram** considera as pessoas presentes no recorte que têm mais de uma combinação de data e culto no histórico até a data final selecionada. Cadastros repetidos na mesma celebração não contam como retorno. Novos e retornos podem se sobrepor quando alguém chega e volta no mesmo período.

O gráfico mensal de primeira visita e retorno conta cada pessoa uma vez por mês; quem teve a primeira visita dentro do recorte daquele mês entra em primeira visita, e as demais pessoas em retorno. Uma pessoa pode aparecer em vários meses. Meses parciais não devem ser comparados como meses completos.

A média de visitantes por culto considera somente celebrações com registro de visitante. Não infere que os demais cultos tiveram zero visitantes. A presença soma as contagens de membros e crianças disponíveis; não representa membros únicos. Ausência de contagem aparece como `—`, e um zero informado continua sendo zero.

Filtros de datas e cultos afetam o painel todo. Busca e status afetam a lista de visitantes e sua exportação. Os períodos de 30/90 dias terminam na última data disponível, incluindo ambos os limites.
