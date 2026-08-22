# LongWriter DSH compatibility entrypoint

This directory is retained so existing `dsh plugin --profile web add
./dsh-native` installations continue to work. Its implementation is now the
optional adapter in `adapters/dsh`; all publication state and gates live in
`packages/core`.

From the repository root:

```bash
pnpm install --no-frozen-lockfile
npm install --global @deepseek-ai/dsh@0.1.0-rc.6
dsh plugin --profile web add ./dsh-native
dsh --profile web
```
