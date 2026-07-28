"""Ingestion Factory: builds the right BaseIngestionProvider from a state's
config dict, so a State Agent never has to know which platform its state
actually uses -- only its `provider_type`.
"""

from __future__ import annotations

from typing import Any

from .accela_provider import AccelaProvider
from .arcgis_provider import ArcGISProvider
from .base_provider import BaseIngestionProvider
from .ckan_provider import CkanProvider
from .energov_provider import EnerGovProvider
from .sam_gov_provider import SamGovProvider
from .socrata_provider import SocrataProvider
from .usaspending_provider import USASpendingProvider


class UnknownProviderType(ValueError):
    pass


def build_provider(state_config: dict[str, Any]) -> BaseIngestionProvider:
    provider_type = state_config.get("provider_type")

    if provider_type == "socrata":
        domain = state_config["endpoint"].split("//", 1)[-1].split("/", 1)[0]
        dataset = state_config["endpoint"].rstrip("/").rsplit("/", 1)[-1].replace(".json", "")
        return SocrataProvider(
            domain=domain,
            dataset=dataset,
            watermark_field=state_config.get("watermark_field", "recordid"),
            hash_fields_list=state_config.get("hash_fields"),
            commercial_where=state_config.get("commercial_where"),
            lookback_days=state_config.get("lookback_days", 30),
            app_token=state_config.get("app_token"),
            date_field=state_config.get("date_field", "processdate"),
            hard_limit=state_config.get("hard_limit", 0),
        )

    if provider_type == "ckan":
        return CkanProvider(
            base_url=state_config["endpoint"],
            resource_id=state_config["resource_id"],
            watermark_field=state_config.get("watermark_field", "_id"),
            hash_fields_list=state_config.get("hash_fields"),
            commercial_where=state_config.get("commercial_where"),
            date_field=state_config.get("date_field", "date_entered"),
            lookback_days=state_config.get("lookback_days", 30),
            hard_limit=state_config.get("hard_limit", 0),
        )

    if provider_type == "arcgis":
        # endpoint is the full .../FeatureServer/{layer}/query-style URL or
        # base .../FeatureServer -- accept either.
        endpoint = state_config["endpoint"]
        layer = state_config.get("layer", 0)
        base_url = endpoint
        for suffix in ("/query", f"/{layer}"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]
        return ArcGISProvider(
            base_url=base_url,
            layer=layer,
            out_fields=state_config.get("out_fields", "*"),
            commercial_where=state_config.get("commercial_where"),
            watermark_field=state_config.get("watermark_field", "OBJECTID"),
            hash_fields_list=state_config.get("hash_fields"),
            include_geometry=state_config.get("include_geometry", True),
            date_field=state_config.get("date_field"),
            date_field_is_string=state_config.get("date_field_is_string", False),
            date_literal_style=state_config.get("date_literal_style", "date"),
            lookback_days=state_config.get("lookback_days", 30),
            hard_limit=state_config.get("hard_limit", 0),
        )

    if provider_type == "sam_gov":
        return SamGovProvider(
            state_code=state_config["state_code"],
            naics_codes=state_config.get("naics_codes"),
        )

    if provider_type == "usaspending":
        return USASpendingProvider(
            state_code=state_config["state_code"],
            psc_codes=state_config.get("psc_codes"),
            award_type_codes=state_config.get("award_type_codes"),
            lookback_days=state_config.get("lookback_days", 730),
        )

    if provider_type == "accela":
        return AccelaProvider(
            state_code=state_config["state_code"],
            county=state_config["county"],
            base_url=state_config["endpoint"],
            permit_type_label=state_config.get("permit_type_label", "Building"),
            module=state_config.get("module", "Building"),
            lookback_days=state_config.get("lookback_days", 30),
            max_pages=state_config.get("max_pages", 30),
            start_date_field_id=state_config.get("start_date_field_id"),
            end_date_field_id=state_config.get("end_date_field_id"),
        )

    if provider_type == "energov":
        return EnerGovProvider(
            state_code=state_config["state_code"],
            county=state_config["county"],
            base_url=state_config["endpoint"],
            tenant_id=state_config.get("tenant_id", "1"),
            tenant_name=state_config.get("tenant_name"),
            commercial_keywords=state_config.get("commercial_keywords"),
            date_field=state_config.get("date_field", "IssueDate"),
            lookback_days=state_config.get("lookback_days", 30),
            max_pages=state_config.get("max_pages", 5),
        )

    if provider_type in ("ckan", "csv"):
        raise NotImplementedError(
            f"provider_type={provider_type!r} is specced but not yet implemented -- "
            "see docs/AGENT_STRATEGY.md / this session's roadmap notes. "
            "Socrata and ArcGIS cover NJ + the immediate next-state rollout; "
            "build CKANProvider/CSVDownloadProvider when a real state needs one, "
            "verified live first (same discipline as every other source this session)."
        )

    raise UnknownProviderType(f"Unknown provider_type: {provider_type!r}")
