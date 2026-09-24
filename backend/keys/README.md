# JWT signing keys

ClientLens uses **RS256** for JWT auth (see `docs/adr/ADR-009-authentication.md`):
the private key **signs** tokens; the public key **verifies** them. This lets other
services (workers, MCP server) verify tokens with only the public key, never holding the
signing secret.

## Local development

The `.pem` files here are **git-ignored** (see root `.gitignore`) and must be generated
locally. They are throwaway dev keys — never reuse them anywhere real.

Generate a dev keypair:

```bash
cd backend
mkdir -p keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out keys/jwt_private_dev.pem
openssl rsa -pubout -in keys/jwt_private_dev.pem -out keys/jwt_public_dev.pem
```

Config points at these paths by default (`Settings.jwt_private_key_path` /
`jwt_public_key_path`).

## Production

Do **not** use file-based dev keys in production. Inject keys via a secrets manager
(env vars / mounted secrets) per SPEC §26/§34, and rotate them. The public key can be
distributed to verifying services; the private key stays only where tokens are issued.
