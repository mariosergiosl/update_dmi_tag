# ROADMAP

## v2.2, Execução paralela (`--parallel N`)

Status: **concluído**. Implementado e validado em campo (`--parallel 3`
contra 3 hosts heterogêneos reais) desde a v2.2.0. Este documento é
mantido como registro histórico da especificação original; o
comportamento real pode ser conferido no código (`__main__.py`,
`_processa_hosts_paralelo`) e na seção 8.6 do `manual_operacao.md`.

### Motivação

Hoje o processamento é sequencial: um host por vez. No Mecanismo 3 (boot
EFI), cada host bloqueia até ~40 a 300 s esperando o reboot voltar, então
um lote grande (por exemplo, 300 alvos) leva muito tempo em fila.

### Desenho

1. **`--parallel N`** (default 1, mantém o comportamento sequencial atual).
   Concorrência limitada por decisão operacional (blast radius): o
   operador escolhe quantos hosts ficam em voo ao mesmo tempo. Nunca
   paralelismo ilimitado, reiniciar todos os hosts ao mesmo tempo é risco.

2. **Workers isolados, um log por host.** Cada host processa numa thread
   do pool e escreve no próprio arquivo de log. Sem estado compartilhado,
   sem lock, sem contenção. A independência é total: cada host tem NVRAM,
   ESP e BBconfig próprios, e a idempotência/limpeza do Mecanismo 3 é por
   host.

3. **Ticker de progresso no stdout.** Conforme cada host finaliza, uma
   linha só na tela, por exemplo:
   `[142/300] 192.168.56.51 -> OK-efiboot (falhas ate agora: 3)`.
   Dá acompanhamento ao vivo sem poluir. Detalhe de um host específico via
   `tail -f` no log dele.

4. **Merge no fim, sem lock.** Terminada a fase paralela, junta os logs
   por host na ordem do `hosts.txt` dentro do consolidado. Ordenado pela
   lista (fácil achar um host), não pela ordem de conclusão. À prova de
   kill: se a ferramenta morrer no meio, os logs por host já estão no
   disco.

5. **Estrutura `logs/<timestamp>/` por execução:**

   ```
   logs/
     20260713_101530/
       consolidado.log
       efi.log
       hosts_inacessiveis.txt
       hosts/
         192.168.56.51.log
         192.168.56.52.log
   ```

   Cada rodada fica auto-contida: deu problema, zipa a pasta daquele
   timestamp e manda para debug, sem misturar com outras execuções e sem
   sujar a raiz do projeto.

### Compatibilidade

- `--log-local` e `--log-efi` explícitos continuam ganhando; só o valor
  default muda para dentro de `logs/<timestamp>/`.
- `.gitignore` passa a ignorar a pasta `logs/`.

### Pontos abertos / futuros

- `--keep-logs N`: podar pastas de log antigas (retenção).
- Modo verbose no paralelo: segurar o stdout por host e imprimir o bloco
  na conclusão (opcional; o ticker já cobre o acompanhamento ao vivo).

### Fluxo de desenvolvimento

Implementar em branch dedicado (por exemplo `feature/parallel-execution`),
mantendo o `main` estável na v2.1.14 (tag `v2.1.14`). Ao concluir e
validar, merge no `main` e nova tag `v2.2.0`.
