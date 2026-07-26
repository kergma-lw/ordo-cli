# Rewriting a piece of `gitx.sh` as Ordo

## Что переписано

Это не полный перенос `gitx.sh`, а **один вертикальный срез**:

- кусок ритуала `set-active-task` from `.local/scripts/gitx.sh`;
- в частности та часть, где сначала проверяются предохранители,
  потом issue переводится в `In progress`,
  потом синхронизируется `main`,
  потом создаётся или выбирается task branch.

См. пример: `examples/set-active-task-from-gitx.yaml`.

## Почему выбран именно этот кусок

Он хорошо показывает, где Ordo может быть сильнее простого shell-скрипта:

1. есть явные **guards**;
2. есть короткая и ревьюемая последовательность **steps**;
3. policy видна прямо в декларации, а не размазана по `if/case/exit`;
4. шаги можно потом исполнять в режимах `check`, `plan`, `execute`, `explain`.

## Что в shell-скрипте здесь выражено неявно

В `gitx.sh` и `oc_gitx.sh` эта логика размазана по:

- `ensure_single_worktree`;
- `ensure_clean_worktree`;
- проверкам issue/project status;
- git sync + branch creation;
- repo-specific policy.

В bash это рабоче, но semantics спрятана в:

- control flow;
- `exit 1/2`;
- текстовые сообщения;
- ручную композицию git/gh команд.

## Как это выглядит в Ordo

```yaml
version: 0
workflow: set-active-task

inputs:
  repository: kergma-lw/checklist-backend
  issue_number: 16
  project_id: PVT_kwDOBQfyUc4A3Q3j
  branch: keep
  iteration: Sprint 12

guards:
  - uses: git.single_worktree
  - git.worktree.clean
  - gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"

steps:
  - name: move-issue-to-in-progress
    uses: gh.project.issue.field_single_select.set
    with:
      repository: ${inputs.repository}
      issue_number: ${inputs.issue_number}
      project_id: ${inputs.project_id}
      status: In progress

  - name: set-current-iteration
    uses: gh.project.issue.field_iteration.set
    with:
      repository: ${inputs.repository}
      issue_number: ${inputs.issue_number}
      project_id: ${inputs.project_id}
      iteration: ${inputs.iteration}

  - name: sync-main
    uses: git.sync.fetch

  - name: create-or-switch-task-branch
    uses: git.branch.switch
    with:
      branch: ${inputs.branch}
```

## Что этот пример показывает

### 1. Ordo хорошо подходит для policy-heavy rituals

Именно такие штуки, как:

- "не работай при нескольких worktree";
- "не начинай задачу из грязного дерева";
- "не начинай, если issue уже Done/In review";

выглядят естественно как guards.

### 2. Разница видна не в YAML как таковом, а в execution shape

Если Ordo просто сделает "ещё один YAML runner", пользы мало.

Польза появляется, если runtime умеет:

- отдельно вычислять guards;
- отдельно строить plan;
- отдельно объяснять, почему workflow blocked;
- возвращать structured result, а не только лог.

### 3. Не всё из `gitx.sh` стоит переносить буквально

В shell-скрипте есть много operational detail, который в Ordo лучше скрыть внутри operations:

- как именно синхронизировать `main`;
- как именно формировать branch name;
- как именно читать GitHub project fields;
- какие именно `git`/`gh` команды вызываются.

Это должно жить в code-level connector operations, а не в workflow YAML.

## Чего этот пример пока не доказывает

Он **не доказывает**, что Ordo уже лучше pypyr или shell.

Он показывает только, что у Ordo есть разумный кандидат на нишу:

- guarded,
- explainable,
- contract-first local rituals.

Если runtime потом сведётся к "выполни набор шагов", преимущество исчезнет.
