# PR-03 answer-extractive-v2 (Answer Agent, deterministic template)

Used by default and in the unattended assessment run. No model is called, so no generated claim can drift from the source.

Template (implemented in `src/cloudserve/agents.py::AnswerAgent.draft`):

1. Disclosure line naming the approved guide, saying the reply was prepared automatically, and saying a person can review it. Ravi asked for automated replies to be identified.
2. "Common causes:" each bullet of the article's Common causes section, followed by that passage ID.
3. "What to do:" each numbered step of the selected Resolution passage, kept complete and in order, followed by its passage ID.
4. "Note:" the article's Notes section, with its passage ID.
5. A closing line saying how to reach a specialist. It makes no refund, fix or timeline promise.

Change from v1: v1 quoted the first 540 characters of the Resolution passage, which cut procedures mid-step.
