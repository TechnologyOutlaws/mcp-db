# Boil the Ocean — Execution Standard (mcp-db)

The answer is the finished product. Not the plan. Not the outline.
The bar is: "holy shit, that's done."

## Rules

1. Plan first. State steps, sequence, done conditions before any code.
2. One task per session. One module, one tool, one fix.
3. Re-plan trigger: same error twice = wrong approach. Stop. New approach.
4. TDD first: test red → implementation → test green. Always.
5. Verify before done: run pytest, confirm green, then call it done.
6. Resolve ambiguity, don't stop on it. Make the best call, flag it.
7. Permanent fix over workaround.
8. No TODO in deliverables. Finish it or name the hard gate.

## Prohibited Patterns

| Never do this                          | Do this instead                  |
|----------------------------------------|----------------------------------|
| "We could table this for later"        | Do it now or name the hard gate  |
| "Here's an outline"                    | Fill it in completely            |
| Third attempt at same failing approach | Stop. Re-plan. New approach.     |
| Calling it done without pytest green   | Run pytest. Then call it done.   |
| TODO in committed code                 | Finish it or name the gate       |
| Asking for info available in the repo  | Read the repo. Answer yourself.  |

## Hard Gates (legitimate stops)

Format: "This requires [named dependency] — confirm and I'll [next output]."

Invalid stops: "This might need more thought." / "Several approaches exist."
