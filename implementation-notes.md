# Implementation Notes

## 2026-06-01: ABSA schema normalization

- Read `AGENTS.md` before coding, as requested.
- The existing project had an early lightweight `models.py` shape using `text` and `aspects`; the requested production input shape is `review_text` plus `annotations[]`. I added the requested schemas in a new `schemas.py` module instead of deleting the older prototype models immediately.
- `data/samples/absa_outputs.jsonl` is being moved to the actual ABSA format so local commands and schema tests exercise the format described in `AGENTS.md`.
- Flattening uses deterministic extraction IDs with zero-based annotation indexes: `f"{review_id}_{annotation_index}"`. The prompt did not specify one-based or zero-based indexing; zero-based matches Python list indexing and keeps the implementation simple.
- `flatten_reviews` receives a loaded label schema instead of reading config internally. This keeps the function deterministic and easier to test.
- `severity` is set to `0.0` exactly as requested. Future severity scoring should replace this in one place during flattening or immediately after flattening.
- Unknown restaurant IDs are filled with the `default_restaurant_id` argument. `restaurant_name`, `rating`, and `review_time` stay optional.
- No internal field named `evidence` is used in the new schemas.
- The CLI reconfigures `stdout` to UTF-8 when supported. This is needed on Windows shells that default to `cp1252`, otherwise Vietnamese sample text can raise `UnicodeEncodeError`.
