#!/bin/sh
set -e

# If running as root, fix ownership of the volume and then drop privileges.
# If already running as a non-root user (e.g., via the `user:` directive in Compose),
# simply execute the command without trying to chown.
if [ "$(id -u)" = "0" ]; then
    # The dash-cache volume is root-owned by default; fix it for the target user.
    # The UID/GID come from the container's runtime configuration.
    chown -R 1000:1000 /cache 2>/dev/null || true

    # Drop from root to the specific UID:GID
    exec gosu 1000:1000 "$@"
fi

exec "$@"
