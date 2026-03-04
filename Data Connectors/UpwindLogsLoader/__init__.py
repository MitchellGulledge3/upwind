"""
Upwind Catalog Loader - Azure Function

Timer-triggered function that fetches Upwind catalog assets and uploads
them to Azure Monitor via Data Collection Rules (DCR).
"""

import logging
from datetime import datetime, timezone

import azure.functions as func
from azure.core.exceptions import HttpResponseError
from azure.identity import ManagedIdentityCredential
from azure.monitor.ingestion import LogsIngestionClient

from .config import load_configuration
from .upwind_catalog_client import UpwindCatalogClient


def _upload_to_dcr(config, assets: list) -> None:
    """
    Upload catalog assets to Azure Monitor via DCR.
    The SDK handles 1MB chunking and gzip compression internally.

    :param config: ConfigStore with Azure DCR configuration.
    :param assets: List of asset dictionaries to upload.
    """

    azure_client_id = config.get("azure_client_id")
    dce_endpoint = config.get("azure_dce_endpoint")
    dcr_immutableid = config.get("azure_dcr_immutableid")
    stream_name = config.get("azure_stream_name")

    credential = ManagedIdentityCredential(client_id=azure_client_id)
    client = LogsIngestionClient(endpoint=dce_endpoint, credential=credential)

    upload_errors = []

    def on_upload_error(error):
        """Callback for per-chunk upload failures."""
        logging.error(
            "Failed to upload chunk of %d logs: %s",
            len(error.failed_logs),
            error.error,
        )
        upload_errors.append(error)

    logging.info(
        "Uploading %d records to DCR %s at %s",
        len(assets),
        dcr_immutableid,
        dce_endpoint,
    )

    client.upload(
        rule_id=dcr_immutableid,
        stream_name=stream_name,
        logs=assets,
        on_error=on_upload_error
    )

    if upload_errors:
        total_failed = sum(len(e.failed_logs) for e in upload_errors)
        logging.error(
            "Upload completed with errors: %d chunks failed, %d total records lost.",
            len(upload_errors),
            total_failed,
        )
        raise RuntimeError(
            f"Upload partially failed: {len(upload_errors)} chunk(s) failed, "
            f"{total_failed} record(s) not uploaded."
        )

    logging.info("All records uploaded successfully.")


def main(mytimer: func.TimerRequest = None) -> None:
    """
    Azure Function entry point (timer-triggered).

    Fetches Upwind catalog assets and uploads them to Azure Monitor
    via the Logs Ingestion API.
    """

    utc_timestamp_start = datetime.now(timezone.utc)
    logging.info(
        "Upwind Catalog Loader: function started at %s",
        utc_timestamp_start.isoformat(),
    )

    if mytimer and mytimer.past_due:
        logging.warning("Upwind Catalog Loader: timer trigger is past due.")

    config = load_configuration()

    try:
        catalog_client = UpwindCatalogClient(config)
        assets = catalog_client.fetch_catalog_assets()

        if not assets:
            logging.info("No catalog assets returned from Upwind API. Nothing to upload.")
            return

        _upload_to_dcr(config, assets)

    except HttpResponseError as e:
        logging.error("Azure Monitor upload failed: %s", e.message)
        if hasattr(e, "response") and e.response:
            logging.error(
                "Response status: %s, body: %s",
                e.response.status_code,
                e.response.text,
            )
        raise
    except Exception as e:
        logging.error("Upwind Catalog Loader failed: %s", e, exc_info=True)
        raise

    utc_timestamp_end = datetime.now(timezone.utc)
    duration = (utc_timestamp_end - utc_timestamp_start).total_seconds()
    logging.info(
        "Upwind Catalog Loader: completed. Duration: %.2fs, Assets uploaded: %d",
        duration,
        len(assets),
    )
