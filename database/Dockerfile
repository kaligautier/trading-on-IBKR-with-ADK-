FROM liquibase/liquibase:5.0.4@sha256:060f96efff4811ccf03957ff3160f21ea04139b89940640f8ad54a065cdc6906
# Pin both the driver release and its bytes; avoid mutable LPM download metadata.
ADD --checksum=sha256:73914527305a40cce504b0d3d90b23caf565136912d607ae8ae7c5895512332c --chmod=0644 \
    https://jdbc.postgresql.org/download/postgresql-42.7.14.jar \
    /liquibase/lib/postgresql-42.7.14.jar
