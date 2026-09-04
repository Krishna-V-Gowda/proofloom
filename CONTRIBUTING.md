# Contributing

Proofloom is a bounded research prototype. Contributions are welcome when they preserve its central separation of authority:

- machine learning may rank ambiguous evidence;
- deterministic controls decide whether financial invariants hold;
- explicit policy and human review retain consequential authority.

Before opening a pull request:

```bash
make setup
make validate
```

Please include a test for every changed financial rule or state transition. New evaluation claims must include the generator/configuration, exact command, raw result, and limitation. Never include real merchant data, production credentials, or copied bank statements.
