# Guard expression data shape

## Stable guard forms

Guards may be expressed either as explicit operation calls or as compact expressions.

### Operation-call form

```yaml
- uses: namespace.name
  with: {}
```

### Expression form

```yaml
- git.worktree.clean and git.branch.value != "main"
```

```yaml
- gh.issue(issue=inputs.issue).project.member
- gh.issue(issue=inputs.issue).status not in ["Done", "In review"]
```

## Expression shape rules

- A string guard item contains a compact boolean policy expression.
- A string guard item is the preferred compact authoring form for expression guards.
- Zero-argument probe references do not require `()`.
- Parameterized probe references use argument syntax only when arguments are present.
- `inputs.name` is the stable input-reference form inside expressions.
- Named arguments are the preferred parameter syntax for probe calls.
- Field access after a probe reference reads probe output fields.
- Boolean-valued probe fields may appear directly as conditions.
- Expression grammar remains intentionally small and dedicated to guard evaluation.

## List semantics

- Multiple string or object guard items may appear in one `guards` list.
- The list structure itself implies conjunction across items.
- Disjunction belongs inside a single expression item rather than in the list structure.

## Coexistence rule

- Both guard forms may coexist during migration if the product needs compatibility between explicit probe calls and compact expression guards.
- The stable contract may allow both object-form guards and string-form guards during migration without requiring a tag field for expression guards.

## Serialization rule

- Guard expression meaning is defined over the loaded workflow model, not over incidental YAML formatting.
- Any parsed guard expression must still map to a losslessly explainable runtime structure.
