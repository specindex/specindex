"""Shared infrastructure for SpecIndex scripts.

Exists because the same infrastructure was copy-pasted across scripts and then
fixed in only one of them. The clearest case: gcs_bucket()'s credential
fallback appears in at least three files, and when the expired-ADC bug was
found -- where every tenant reported "0 documents uploaded" because a user
credential had expired and the script was discarding a WORKING service-account
key -- the fix landed in one copy. The other copies kept failing in a way that
reads as "this source has no documents".

Modules:
    storage   GCS bucket with credential preference and object-level probing
    db        Postgres connections and the pipeline_runs / work_queue contracts
    http      HTTP with a MANDATORY soft-404 baseline per host
    progress  rate + ETA logging for long loops
"""
