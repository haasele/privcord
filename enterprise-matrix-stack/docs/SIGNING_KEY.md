# Synapse signing key (main + workers)

Main Synapse and worker pods both use the **same signing key** from the Kubernetes Secret `synapse-signing-key` (key `signing.key`). You must create this Secret before starting Synapse.

## Generate the key

Generate a signing key (one-time, or reuse an existing homeserver signing key):

```bash
# Using Synapse (if installed), or generate a 256-bit key
python3 -c "
import base64, os
key = base64.b64encode(os.urandom(32)).decode()
print(key)
"
```

Save the output (or the contents of an existing `signing.key` file).

## Create the Secret

Put the key into `k8s/base/secrets.yaml` under the `synapse-signing-key` Secret, or create the Secret directly:

```bash
kubectl create secret generic synapse-signing-key -n matrix-stack \
  --from-file=signing.key=/path/to/signing.key
```

If using `secrets.yaml`: set `stringData.signing.key` to the raw key content (or base64). Then `kubectl apply -f k8s/base/secrets.yaml`.

Both the main Synapse deployment and the synapse-workers StatefulSet mount this Secret at `/data/signing.key`; they will not start correctly until the Secret exists.
