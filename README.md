# One Pager — Liqi Digital Assets

Aplicação HTML interativa para geração de One Pagers de operações estruturadas da **Liqi Digital Assets**.

## Funcionalidades

- Todos os campos editáveis diretamente no browser (sem necessidade de backend)
- 8 seções completas fiel ao template oficial:
  1. Resumo da Operação
  2. Fluxograma da Estrutura
  3. Revolvência
  4. Garantia
  5. Datas · Amortização · Remuneração · Fundos
  6. Ordem de Alocação de Recursos (Cascata Ordinária e Extraordinária)
  7. Fee Liqi
  8. Informações Adicionais
- Exportação para PDF via impressão do browser
- Botão para limpar e restaurar campos padrão

## Como usar

### Opção 1 — Abrir direto no browser

Abra o arquivo `onepager-liqi.html` em qualquer navegador moderno.

### Opção 2 — Servidor local

```bash
cd OnePager_Liqi
python3 -m http.server 8080
```

Acesse: [http://localhost:8080/onepager-liqi.html](http://localhost:8080/onepager-liqi.html)

## Exportar como PDF

Clique no botão **"Imprimir / Exportar PDF"** e selecione "Salvar como PDF" na janela de impressão do navegador.

## Estrutura

```
OnePager_Liqi/
└── onepager-liqi.html   # Aplicação completa (HTML + CSS + JS em arquivo único)
```

---

**Liqi Digital Assets** · Estruturação de Ativos · CNPJ 41.743.644/0001-57
