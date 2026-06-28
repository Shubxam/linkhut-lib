"""Test configuration.

The library reads `LH_PAT` and `LINK_PREVIEW_API_KEY` from the environment at
request time. Tests should not depend on real credentials; the unit tests in
this directory exercise pure helpers and Pydantic models only, so no fixtures
are needed.
"""
