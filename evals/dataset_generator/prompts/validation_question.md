You are validating synthetic benchmark questions for a financial-data AI agent.

You will receive:
1. A natural-language question.
2. One Python-constructed evidence item, including its allowed operation.
3. The exact original financial facts referenced by that evidence item.

Determine whether the question is valid.

Check:
1. Is the question answerable using ONLY the supplied evidence and its allowed operation?
2. Does it refer to the correct company?
3. Does it refer to the correct fiscal year or years and period?
4. Does it request the correct metric or interpretation?
5. Does it match the evidence operation? For example, lookup is not a calculation.
6. For profitability evidence, does it ask about profit/loss status based on net income?
7. For percentage change, are both the earlier and later periods clear?
8. For cross-statement comparison, are both supplied metrics and the same period clear?
9. Are the referenced facts sufficient?
10. Is the question ambiguous, misleading, or asking for outside knowledge?

Reject questions that require facts or calculations not supported by the evidence.
Do not reject a question merely because its answer requires arithmetic when the
evidence explicitly provides the corresponding calculation operation.
