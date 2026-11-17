# Application layer

Use cases that coordinate domain rules, ports and orchestration. Must not import the API layer.

- `use_cases/process_ticket.py`: the ticket use case shared by the API and the batch harness (`TicketService`).
- `use_cases/govern_knowledge.py`: staging, steward review with retry/dead-letter, certification, publication.
- `use_cases/deliver_messages.py`: transactional-outbox dispatcher.
- `reliability.py`: bounded retry with exponential backoff and jitter.
