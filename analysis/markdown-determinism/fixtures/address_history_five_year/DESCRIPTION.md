# Five-year address-history fixture

This fixture is the next increment after `address_history_conversation`.

It keeps the dialogue-style evidence and similar output structure, but adds written
business rules that determine which candidate addresses belong in the submitted
form.

The model must:

- derive a five-year history window from the July 2026 application month
- include addresses occupied at any point during that window
- include Sheffield because its occupation overlaps the July 2021 cutoff
- preserve Sheffield's actual March 2020 move-in month
- exclude Derby because the occupation ended before the cutoff
- exclude Birmingham under the temporary work-accommodation rule
- exclude correspondence, family, workplace and travel addresses
- reconcile the corrected York and Hull details
- order included previous addresses from most recent to oldest
- calculate months at each included previous address

The tool schema and expected arguments have been validated with JSON Schema.