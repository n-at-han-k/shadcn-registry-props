# shadcn-registry-props

A daily snapshot of the public [shadcn registry directory](https://ui.shadcn.com/r/registries.json)
and every registry's full index.

## What it does

[`.github/workflows/update.yml`](.github/workflows/update.yml) (via
[`update.py`](.github/workflows/update.py)) runs on a daily schedule (and on
manual dispatch):

1. Fetches the directory at `https://ui.shadcn.com/r/registries.json` — an array
   of `{ name, homepage, url, description }`.
2. For each registry, resolves its index by substituting the `{name}` placeholder
   in the registry's `url` template with `registry` (falling back to `index`),
   e.g. `https://7ovr.com/r/{name}.json` → `https://7ovr.com/r/registry.json`.
3. Saves each registry's index to the repo root as `<name>.json` (the leading
   `@` is stripped, so `@ai-elements` → `ai-elements.json`). The directory itself
   is saved as `registries.json`.

Each saved index follows the shadcn registry schema:
`{ "$schema", "name", "homepage", "items": [...] }`, where `items` lists every
component/block with its `files`, `dependencies`, `registryDependencies`, and
`type`.

## Running locally

```bash
python .github/workflows/update.py
```
