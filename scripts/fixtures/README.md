# Published documentation snapshots

These files are frozen inputs for the website's downloadable manuals and
retrospectively mapped rewards. Live prompts and scoring are owned by the Physim
environment in the residency repository. The installed environment never imports
these documentation fixtures.

All three files are byte-for-byte copies from physim repo commit
`915497cec4c4c10afb87ff4a61993f0aaa660a51`, before removal of the duplicated package.
The main manual also matches the previously recorded `26d9f41` snapshot.

| Fixture | Original path under `environments/physim/physim/` | SHA-256 |
|---|---|---|
| `published_agent_spec.txt` | `data/agent_spec.txt` | `27e431c3aecabb8efc6fb29d907635eca9040ae24b453f16f088c3c8959a494a` |
| `published_agent_spec_v1.txt` | `data/agent_spec_v1.txt` | `04b8480edf8b73038d9f26a92a06141edc06f139b46a73ff67aa7f4421cbae90` |
| `published_rewards.py` | `rewards.py` | `bf12a3e87792f5df33cd64bac87c78f52d9d12580e36be0a3e596b9027453b0c` |

`scripts/check_docs.py` verifies both template hashes and renders their reviewed
example settings for comparison with `docs_source/examples/AGENT_SPEC*.md`; it
also checks that the published downloads match those source files. The V1
download's stale reciprocal-reward paragraph is corrected to match its template's
logarithmic reward. All other manual text is preserved.

`scripts/build_docs.py` verifies the reward helper's hash before loading it with
the Python standard library. The existing calibration check still requires the
published target K to match the reviewed evidence. No installed package is needed
to build or check the website.

Changing an environment pin does not refresh these snapshots. Any deliberate
publication revision must review the source commit, hashes, example text, and
derived evidence together. Formatters exclude this directory to preserve bytes.
